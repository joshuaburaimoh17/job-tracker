import re

_US_STATES = [
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York', 'North Carolina',
    'North Dakota', 'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania',
    'Rhode Island', 'South Carolina', 'South Dakota', 'Tennessee', 'Texas',
    'Utah', 'Vermont', 'Virginia', 'Washington', 'West Virginia',
    'Wisconsin', 'Wyoming',
]

_US_CITIES = [
    'San Francisco', 'Los Angeles', 'New York City', 'NYC', 'Chicago',
    'Boston', 'Seattle', 'Austin', 'Denver', 'Atlanta', 'Houston',
    'Dallas', 'Phoenix', 'Portland', 'San Diego', 'Minneapolis',
]

_MISMATCH_PATTERNS = (
    [re.compile(r'\b' + re.escape(s) + r'\b', re.IGNORECASE) for s in _US_STATES + _US_CITIES]
    + [
        re.compile(r'must be (based|located|residing) in', re.IGNORECASE),
        re.compile(r'\bUS only\b|\bUnited States only\b', re.IGNORECASE),
        re.compile(r'\bUS (citizens?|residents?)\b', re.IGNORECASE),
    ]
)


def has_location_mismatch(lead) -> bool:
    text = ' '.join([
        getattr(lead, 'location', '') or '',
        getattr(lead, 'job_description', '') or '',
    ])
    return any(p.search(text) for p in _MISMATCH_PATTERNS)
