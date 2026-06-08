import aioimaplib

async def connect(host, port, credentials):
    """Подключается к IMAP-серверу и логинится через переданный объект Credentials.

    Сам движок не знает, пароль это или OAuth-токен — авторизацию выполняет
    credentials.login(client) (см. auth/credentials.py).
    """
    client = aioimaplib.IMAP4_SSL(host=host, port=port)
    await client.wait_hello_from_server()

    response = await credentials.login(client)
    if response.result != "OK":
        await disconnect(client)
        raise ConnectionError(f"Не удалось авторизоваться на {host}:{port} ({credentials.email}): {response.result}")

    await client.select("INBOX")
    return client

async def disconnect(client):
    try:
        await client.logout()
    except Exception:
        pass

async def test_login(host, port, credentials):
    """Пробное подключение для веб-формы: проверяет данные и сразу закрывает соединение."""
    client = await connect(host, port, credentials)
    await disconnect(client)
