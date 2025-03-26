# Image -> Fiche !

The purpose of this tool is to translate both images from the AlterEgo A1 textbook, as well as formatted text (Markdown), into Anki-compatible flash cards.

## Importing to Anki

All text files in [anki-imports](./anki-imports) can be directly imported into Anki simply by using the "File -> Import" menu buttons, then selecting whichever text files you'd like.

## Sources

The [grammaire](./grammaire) and [lexique](./lexique) folders contain the source text / images, as well as the schemas / prompts utilized by the models to develop the intermediate forms and final JSON outputs, which are then translated into a CSV-style format.

## Outputs

In [anki-imports/lexique](./anki-imports/lexique), there are flash cards generated from slightly modified images in the A1 textbook glossary, which are located in [lexique/A1](./lexique/A1/).

Currently there are no sources in [grammaire](./grammaire), but I am planning to create a schema to make grammar related flash cards using the 'grammaire' appendix pages in the A1 textbook.

\* The outputs will follow the same format: `./anki-imports/grammaire`

## Generation

**Usage**

```text
usage: main [-h] -apikey APIKEY -schema SCHEMA -outd OUTPATH [-model MODEL] [-text [TEXTS]] [-image [IMAGES]] [-prompt PROMPT]
```

The program expects to receive a `schema` prompt, which will be the translation promptfor any source text to convert into an expected flash card JSON schema output.

If images are passed, then both the `schema` and `prompt` prompts are required to be passed, with the `prompt` input representing the OCR requirements going from image to output markdown.

\* _This program requires the use of an OpenRouter API key; create one here: [OpenRouter API key](https://openrouter.ai/settings/keys)_

\* _You can specify your own LLM with the `model` flag, replacing the default: `Gemma 3 27B LLM`._
