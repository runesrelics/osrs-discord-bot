# Layout configuration for listing templates

# Profile picture settings
PFP_CONFIG = {
    'size': (70, 70),          # Size of the profile picture (width, height)
    'position': (25, 25),      # Position of profile picture (x, y from top-left)
}

# Text settings
TEXT_CONFIG = {
    'username': {
        'position': (110, 45),  # Position of username text
        'font_size': 24,        # Font size for username
        'color': (255, 255, 255),  # RGB color (white)
    },
    'price': {
        'position': (550, 45),  # Position of price text
        'font_size': 24,        # Font size for price
        'color': (255, 255, 255),  # RGB color (white)
        'right_padding': 30,    # Padding from right edge
    },
    'description': {
        'position': (50, 200),  # Position of description text
        'font_size': 24,        # Font size for description
        'color': (255, 255, 255),  # RGB color (white)
        'max_width': 700,       # Maximum width for text wrapping
        'line_spacing': 5,      # Space between lines
    },
    'account_type': {
        'position': (550, 1150),  # Position of account type label
        'font_size': 24,          # Font size for account type
        'color': (0, 255, 255),   # RGB color (cyan)
        'right_padding': 30,      # Padding from right edge
    }
}

# Showcase image settings
SHOWCASE_CONFIG = {
    'max_height': 300,         # Maximum height of showcase image
    'max_width': 700,         # Maximum width of showcase image
    'position': (50, 800),    # Position of showcase image (x, y)
    'padding': 50,            # Padding from edges
}