import re

# Adding a level: edit only this dict. VALID_LEVELS and the SQL CASE in
# log_query_builder are derived. Synonyms (WARN/WARNING, CRIT/CRITICAL)
# share a rank.
LEVEL_RANK: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "WARNING": 30,
    "ERROR": 40,
    "CRIT": 50,
    "CRITICAL": 50,
}

VALID_LEVELS: frozenset[str] = frozenset(LEVEL_RANK.keys())

KV_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_.]+$")
