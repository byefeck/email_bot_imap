from bs4 import BeautifulSoup

def clean_html(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")

    for tag in soup(["script", "style", "noscript", "img"]):
        tag.decompose()

    for tag in soup.find_all(attrs={"style": True}):
        if "display:none" in tag.get("style", ""):
            tag.decompose()

    for br in soup.find_all("br"):
        br.replace_with("\n")

    text = soup.get_text(separator="\n")

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    cleaned = []
    for line in lines:
        if "unsubscribe" in line.lower():
            continue
        if "let us know" in line.lower():
            continue
        cleaned.append(line)

    return "\n".join(cleaned)