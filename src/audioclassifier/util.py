import hashlib


def generate_hash(source, name):
    return hashlib.sha256((source + name).encode()).hexdigest()


def sanitize_name(name):
    for char in '/\\:*?"<>| ':
        name = name.replace(char, "_")
    return name
