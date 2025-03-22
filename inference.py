import base64
import itertools
import json
import pathlib
import threading
import time

from PIL import Image
from io import BytesIO
from sys import exit as sysexit

from openai import OpenAI, Stream

from openai.types.chat import ChatCompletionChunk

confirmation_prompt = """\
Were you able to fully generate the expected output? If not, \
please attempt to start at the vocabulary word that was last \
generated in the previous response, and no earlier.
"""

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

def encode_image(image_path: pathlib.Path):
    img = base64.b64encode(image_path.read_bytes())
    return img.decode()

def image_format(source: str):
    data = base64.b64decode(source)
    img = Image.open(BytesIO(data))
    return img.format.lower()

def sanitize_response(message: str) -> dict:
    """
    As the response is expected to be JSON, ensure that it
    is a valid output, and any extra information is removed.
    """
    try:
        message = message.strip()
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

        1. (`image=False`) Generate a JSON schema representing flash cards according to the text source.

        2. (`image=True`) Generate an OCR translation of the source image into a markdown-style text containing original vocabulary.

    Returns the final output text, which is expected to be valid JSON representing each flash card.
    """

    def setup_spinner(prefix: str=''):
        """Separate thread to loop a spinner while waiting for API call."""

        def spinner(stop_event: threading.Event):
            spinner = itertools.cycle(['-', '\\', '|', '/'])
            while not stop_event.is_set():
                print(f'\033[2K{prefix} {next(spinner)}', end='\r', flush=True)
                time.sleep(0.2)
            print('\003[2K', end='\r', flush=True)

        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=spinner, args=(stop_event,))
        spinner_thread.start()
        return spinner_thread, stop_event

    def openai_read_chunks(response: Stream[ChatCompletionChunk]):
        message = f''
        for chunk in response:
            choices = chunk.choices
            if choices and len(choices) > 0:
                delta = choices[0].delta
                if delta and hasattr(delta, 'content'):
                    message += delta.content
        return message

    def spin_on_api_call(messages, prefix=''):
        thread, event = setup_spinner(prefix)
        try:
            response = client.chat.completions.create(
                model=model, messages=messages, stream=True)
            message = openai_read_chunks(response)
        except Exception as e:
            sysexit(str(e))
        event.set()
        thread.join()
        return message

    if not model:
        model = "google/gemma-3-27b-it:free"

    if image:
        fmt = image_format(source)
        user_prompt = [
            { "type": "text", "text": "Follow the developer prompt." },
            { "type": "image_url", "image_url": f'data:image/{fmt};base64,{source}' }
        ]
    else:
        user_prompt = source

    messages = [
        { "role": "developer", "content": dev_prompt },
        { "role": "user", "content": user_prompt }
    ]

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=apikey)

    message = spin_on_api_call(messages, prefix=('Querying LLM for' +
              (' JSON generation' if not image else ' Markdown generation')))

    if not image:
        return sanitize_response(message)

    messages.extend([
        { "role": "assistant", "content": message },
        { "role": "user", "content": confirmation_prompt}
    ])
    return spin_on_api_call(messages, prefix="Querying LLM to confirm the output is satisfactory")

def text_inferences(apikey: str, model: str, schema: str, textpaths: list[pathlib.Path]):
    for path in textpaths:
        yield (path.stem.lower(), model_inference(apikey, model, schema, path.read_text()))

def image_inferences(apikey: str, model: str, prompt: str, schema: str, imgpaths: list[pathlib.Path]):
    for path in imgpaths:
        response = model_inference(apikey, model, prompt, encode_image(path), image=True)
        yield (path.stem.lower(), model_inference(apikey, model, schema, response))
