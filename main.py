import argparse
import pathlib

from itertools import chain
from sys import exit as sysexit

import inference as inf

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

def main():
    parser = argparse.ArgumentParser(
        prog='Image-A-Fiche',
        description=(
            'Generates Anki style text files for use as flash cards from Alter Ego glossary pages.\n'
            '\nThe program expects to receive a `schema` prompt, which will be the translation prompt'
              'for any source text to convert into an expected flash card JSON schema output.\n'
            '\nIf images are passed, then both the `schema` and `prompt` prompts are required to be passed,'
              'with the `prompt` input representing the OCR requirements going from image to output markdown.\n'
            '\n* You can specify your own LLM with the `model` flag, replacing the default Gemma 3 27B LLM.\n'
            '\n* This program requires the use of an OpenRouter API key; create one here: https://openrouter.ai/settings/keys.\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('-apikey', type=str, dest='apikey', required=True,
                        help="OpenRouter API key to enable connection with the OpenRouter API.")
    parser.add_argument('-schema', type=str, dest="schema", required=True,
                        help="Assistant prompt utilized when translating from markdown to flash card.")
    parser.add_argument('-outd', type=str, dest="outpath", required=True,
                        help="Directory to output the generated flash card text files.")

    parser.add_argument('-model', type=str, dest='model', default="google/gemma-3-27b-it:free",
                        help="The model to process files and images; must be available on OpenRouter.")

    parser.add_argument('-text', type=str, nargs="?", action="append", dest="texts", default=[],
                        help="Markdown or text file(s) that will be parsed to generate flash cards.")

    parser.add_argument('-image', type=str, nargs="?", action="append", dest="images", default=[],
                        help="Image file(s) that will be parsed to generate flash cards.")
    parser.add_argument('-prompt', type=str, dest="prompt", default=None,
                        help="Assistant prompt utilized when translating from images to markdown.")

    args = parser.parse_args()


    try:
        apikey = str(args.apikey)
        model = str(args.model)
        outdir = pathlib.Path(args.outpath).resolve()

        schema_path = pathlib.Path(args.schema).resolve()
        schema = schema_path.read_text()

        imgpaths = [pathlib.Path(p).resolve() for p in args.images]
        textpaths = [pathlib.Path(f).resolve() for f in args.texts]

        prompt = ''
        if args.prompt is not None:
            prompt_path = pathlib.Path(args.prompt)
            prompt = prompt_path.read_text()
    except Exception as e:
        sysexit(str(e))

    if imgpaths and prompt == '':
        sysexit('cannot execute image inference without the `prompt` argument')

    json_schemas = chain(
        inf.text_inferences(apikey, model, schema, textpaths),
        inf.image_inferences(apikey, model, prompt, schema, imgpaths)
    )

    for name, schema in json_schemas:
        fname = f'les_fiches_{name}.txt'
        path = pathlib.Path(outdir / fname)
        card_file_text = create_anki_file(schema)
        path.write_text(card_file_text, encoding='utf-8')
        print(f'Generated {fname}')

if __name__ == '__main__':
    main()
