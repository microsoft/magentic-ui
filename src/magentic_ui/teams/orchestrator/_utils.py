def is_accepted_str(user_input: str) -> bool:
    LIST_OF_ACCEPTED_STRS = [
        "accept",
        "accepted",
        "acept",
        "run",
        "execute plan",
        "execute",
        "looks good",
        "do it",
        "accept plan",
        "accpt",
        "run plan",
        "sounds good",
        "i don't know. use your best judgment.",
        "i don't know, you figure it out, don't ask me again.",
    ]
    user_input = user_input.lower()
    user_input = user_input.strip()
    if user_input in LIST_OF_ACCEPTED_STRS:
        return True
    return False
