THEMES = {
    'dark': {
        'bg': (36, 30, 39),
        'font_colors': [
            (100, 100, 100),
            (180, 180, 180),
            (225, 225, 225),
            (158, 219, 123)
        ],
        'fill_colors': [
            (56, 50, 59),
            (200, 180, 30),
            (110, 0, 200)
        ]
    },
    'light': {
        'bg': (240, 240, 240),
        'font_colors': [
            (168, 168, 168),
            (10, 10, 10),
            (10, 10, 10),
            (158, 219, 123)
        ],
        'fill_colors': [
            (225, 225, 225),
            (220, 220, 60),
            (151, 23, 255)
        ]
    }
}

DEFAULT_THEME = 'dark'

def get_theme(theme = DEFAULT_THEME):
    return THEMES[theme]
