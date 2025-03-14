import json

def create_anki_file(cards: dict[str, dict[str, dict[str, dict[str, str]]]]):
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

if __name__ == '__main__':
    with open('Dossiers.json') as f:
        cards = json.load(f)
    anki_file = create_anki_file(cards)
    with open('LesFichs.txt', 'w') as w:
        w.write(anki_file)
