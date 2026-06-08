import re

def parse_sender(sender):
    email = re.search(r"<(.+?)>", sender)
    email = email.group(1) if email else ""
    name = re.sub(r"<.+?>", "", sender).replace('"', "").strip()
    return name, email
