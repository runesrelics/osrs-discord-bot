# Layout configuration for listing templates

# Font sizes (significantly increased)
FONT_SIZES = {
    'username': 72,     # Very large for username
    'price': 64,       # Large for price
    'description': 52  # Medium for description
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
        'color': (255, 255, 255),  # RGB color (white)
    },
    'price': {
        'position': (550, 35),  # Adjusted position for larger font
        'font_size': FONT_SIZES['price'],
        'color': (255, 255, 255),  # RGB color (white)
        'right_padding': 30,    # Padding from right edge
    },
    'description': {
        'position': (50, 200),  # Position of description text
        'font_size': FONT_SIZES['description'],
        'color': (255, 255, 255),  # RGB color (white)
        'max_width': 700,       # Maximum width for text wrapping
        'line_spacing': 15,      # Increased line spacing
    },
    'account_type': {
        'position': (550, 1150),  # Position of account type label
        'font_size': 52,          # Large font for account type
        'color': (0, 255, 255),   # RGB color (cyan)
        'right_padding': 30,      # Padding from right edge
    }
}

# GP Listing specific configurations
GP_FONT_SIZES = {
    'username': 32,      # Discord server name (reduced to fit in bounds)
    'price': 36,         # Price per M (reduced)
    'vouches': 36,       # Vouch count (reduced)
    'amount': 42,        # Amount (e.g., 2B) (reduced)
    'payment': 42        # Payment method (reduced)
}

GP_TEXT_CONFIG = {
    'username': {
        'font_size': GP_FONT_SIZES['username'],
        'color': (255, 255, 255),  # White
    },
    'price': {
        'font_size': GP_FONT_SIZES['price'],
        'color': (255, 255, 255),  # White
    },
    'vouches': {
        'font_size': GP_FONT_SIZES['vouches'],
        'color': (255, 255, 255),  # White
    },
    'amount': {
        'font_size': GP_FONT_SIZES['amount'],
        'color': (255, 255, 255),  # White
    },
    'payment': {
        'font_size': GP_FONT_SIZES['payment'],
        'color': (255, 255, 255),  # White
    }
}