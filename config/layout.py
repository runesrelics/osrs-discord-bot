# Layout configuration for listing templates

# Font sizes (significantly increased)
FONT_SIZES = {
    'username': 35,     # Very large for username
    'price': 35,       # Large for price
    'description': 35  # Medium for description
}

# Profile picture settings
PFP_CONFIG = {
    'size': (70, 70),          # Size of the profile picture (width, height)
    'position': (25, 25),      # Position of profile picture (x, y from top-left)
}

# Text settings
TEXT_CONFIG = {
    'username': {
        'position': (110, 35),  # Adjusted position for larger font
        'font_size': FONT_SIZES['username'],
        'color': (231, 185, 57),  # RGB color (white)
    },
    'price': {
        'position': (550, 35),  # Adjusted position for larger font
        'font_size': FONT_SIZES['price'],
        'color': (231, 185, 57),  # RGB color (white)
        'right_padding': 30,    # Padding from right edge
    },
    'description': {
        'position': (50, 200),  # Position of description text
        'font_size': FONT_SIZES['description'],
        'color': (231, 185, 57),  # RGB color (white)
        'max_width': 700,       # Maximum width for text wrapping
        'line_spacing': 15,      # Increased line spacing
    },
    'account_type': {
        'position': (550, 1150),  # Position of account type label
        'font_size': 48,          # Large font for account type
        'color': (231, 185, 57),   # RGB color (cyan)
        'right_padding': 30,      # Padding from right edge
    }

}


