import argparse
import base64
import itertools
import json
import pathlib
import threading
import time

from PIL import Image

from openai import OpenAI

img_prompt_path = pathlib.Path(__file__).parent / 'img_prompt.txt'
file_prompt_path = pathlib.Path(__file__).parent / 'file_prompt.txt'

confirmation_prompt = """\
Were you able to fully generate the expected output? If not, \
please attempt to start at the vocabulary word that was last \
generated in the previous response, and no earlier.
"""

# Create an infinite spinner cycle
spinner = itertools.cycle(['-', '/', '|', '\\'])

def encode_image(image_path: pathlib.Path):
    pil_img = Image.open(image_path)
    img = base64.b64encode(image_path.read_bytes())
    return pil_img.format.lower(), img.decode('utf-8')

def create_anki_file(cards: dict[str, dict[str, dict[str, dict[str, str]]]]):
    """
    Simple method to convert the flash card JSON into a 
    CSV-style text that can be parsed by Anki's import service.
    """
    lines = [
        '#separator:|',
        '#html:true',
    ]
    for chapter, chapter_cards in cards.items():
        for lesson, lesson_cards in chapter_cards.items():
            for header, flash_cards in lesson_cards.items():
                for front, back in flash_cards.items():
                    tags = map(lambda s: s.replace(' ', '-').lower(), [
                        chapter, header, f'{chapter} {lesson}',
                    ])
                    lines += [f'{front}|{back}|{" ".join(tags)}']
    return '\n'.join(lines) + '\n'

def attempt_message_join(truncated_message: str, new_message: str):
    """
    Attempts to find the point at the end of the truncated message to place
    the new message at, and returns a concatenated message with proper placement. 
    """
    truncated_reverse = ''.join(reversed(truncated_message))

    # Start with the entire string to attempt to find at the end of the source,
    # then reduce in scope until we (hopefully) find the substring in question.
    n = len(new_message)
    while n > 0:
        substring = ''.join(reversed(new_message[:n]))
        if (index := truncated_reverse.find(substring)) >= 0:
            stopn = len(truncated_message) - (n + index)
            return truncated_message[:stopn] + new_message
        n -= 1
    return ''

def sanitize_response(message: str) -> dict:
    """
    As the response is expected to be JSON, ensure that it 
    is a valid output, and any extra information is removed.
    """
    try:
        message = message.lstrip()
        # Attempt to decode immediately 
        return json.loads(message)
    except json.JSONDecodeError:
        pass
    if not message.startswith('```json') and message[-3:] == '```':
        raise json.JSONDecodeError('invalid formatting from LLM response...')
    try:
        return json.loads(message[7:-3])
    except json.JSONDecodeError:
        return json.loads('{' + message[7:-3] + '}')

def model_inference(apikey: str, model: str, dev_prompt: str, source: str, image: bool=False):
    """
    Using the given developer prompt (<file_prompt.txt | <img_prompt.txt), attempts to do the following:

        1. (`image=False`) Generate a JSON schema representing flash cards according to the lesson given a text source.

        2. (`image=True`) First, generate an OCR translation of the source image into a markdown-style text containing original vocabulary, then follow option 1.
    
    Returns the final output text, which is expected to be valid JSON representing each flash card.
    """

    def setup_spinner():
        """Separate thread to loop a spinner while waiting for API call."""

        def spinner(stop_event: threading.Event):
            spinner = itertools.cycle(['-', '\\', '|', '/'])
            while not stop_event.is_set():
                print(next(spinner), end='\r', flush=True)
                time.sleep(0.2)            

        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=spinner, args=(stop_event,))
        spinner_thread.start()
        return spinner_thread, stop_event

    def spin_on_api_call(messages):
        message = ""
        response = client.chat.completions.create(
            model=model, messages=messages, stream=True)
        thread, event = setup_spinner()
        for chunk in response:
            choices = chunk.choices
            if choices and len(choices) > 0:
                delta = choices[0].delta
                if delta and hasattr(delta, 'content'):
                    message += delta.content
        event.set()
        thread.join()
        return message

    if not model:
        model = "google/gemma-3-27b-it:free"
    
    if image:
        fmt, img = encode_image(source) 
        user_prompt = [
            { "type": "text", "text": "Follow the developer prompt." },
            { "type": "image_url", "image_url": f'data:image/{fmt};base64,{img}' }
        ]
    else:
        user_prompt = source
    
    messages = [
        { "role": "developer", "content": dev_prompt },
        { "role": "user", "content": user_prompt }
    ]

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=apikey)
    
    message = spin_on_api_call(messages)
    
    if not image:
        return sanitize_response(message)

    messages.extend([
        { "role": "assistant", "content": message },
        { "role": "user", "content": confirmation_prompt}
    ])
    return spin_on_api_call(messages)


def main():
    parser = argparse.ArgumentParser(
        add_help=False, prog='Image-A-Fiche',
        description=('Generates Anki style text files for use as'
                    ' flash cards from Alter Ego glossary pages.'),
    )
    parser.add_argument('-apikey', type=str, dest='apikey', required=True, default='',
                        help="OpenRouter API key to enable interface with the OpenRouter API.")
    parser.add_argument('-model', type=str, dest='model', default="google/gemma-3-27b-it:free",
                        help="The model to process files and images; must be available on OpenRouter.")
    parser.add_argument('-file', type=pathlib.Path, nargs="?", action="append", dest="files", default=[],
                        help="Text file(s) that will be parsed to generate flash cards.")
    parser.add_argument('-image', type=pathlib.Path, nargs="?", action="append", dest="images", default=[],
                        help="Image file(s) that will be parsed to generate flash cards.")
    parser.add_argument('-outd', type=pathlib.Path, dest="outpath",
                        help="Directory to output the generated flash card text files.")

    dev_img_prompt = img_prompt_path.read_text()
    dev_file_prompt = file_prompt_path.read_text()

    args = parser.parse_args()
    
    json_schemas = []
    for imgpath in args.images:
        response = model_inference(args.apikey, args.model, dev_img_prompt, imgpath.read_text(), image=True)
        json_schemas.append(
            (imgpath.stem.lower(), model_inference(args.apikey, args.model, dev_file_prompt, response))
        )
    for filepath in args.files:
        json_schemas.append(
            (filepath.stem.lower(), model_inference(args.apikey, args.model, dev_file_prompt, filepath.read_text()))
        )

    for name, schema in json_schemas:
        path = pathlib.Path(args.outpath / f'fiches_de_{name}.txt')
        card_file_text = create_anki_file(schema)
        path.write_text(card_file_text, encoding='utf-8')

if __name__ == '__main__':
    main()
