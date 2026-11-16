"""Event names for column I of the Statements tab.
Copied from the 'event types' tab of the Finances sheet (16 Nov 2026). Keep the two in step:
when the treasurer types a new event on the page, the page tells her to add it to that tab."""

EVENT_TYPES = [
    'Globen',
    'Festival 24',
    'Workshop Thamyra',
    'Concert February',
    'Beginner classes',
    'Rooftop Party',
    'liability',
    'Concert October',
    'Christmas party',
    'Concert Claudia Rabeca',
    'Concert Bigote de Fino',
    'Wineyard',
    'Workshop Joao',
]

# Filled in automatically on lines the page books itself (Holger, 16 Nov 2026).
AUTO_EVENTS = {"Entrance fee sales": "Globen", "Globen vouchers": "Globen", "Classes sales": "Beginner classes"}

# Lines that never belong to an event (Holger, 16 Nov 2026): fees and the club's running costs.
NO_EVENT = {"Zettle fee", "Mobilepay fee", "Billetfix fee", "Bank fee", "Loan (liability)",
            "Transfer between own accounts", "Interest income, bank", "Interest expense, bank",
            "E-conomic costs", "Webpage and domain"}
