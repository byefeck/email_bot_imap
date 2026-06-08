from abc import ABC, abstractmethod

class Credentials(ABC):
    """Способ авторизации на IMAP-сервере. IMAP-движок знает только этот интерфейс."""

    auth_method: str

    def __init__(self, email):
        self.email = email

    @abstractmethod
    async def login(self, client):
        """Авторизует client (aioimaplib.IMAP4_SSL) на сервере."""
        ...

class PasswordCredentials(Credentials):
    auth_method = "password"

    def __init__(self, email, password):
        super().__init__(email)
        self.password = password

    async def login(self, client):
        response = await client.login(self.email, self.password)
        return response

# Точка расширения на будущее: OAuth поверх IMAP (SASL XOAUTH2) для Gmail/Mail.ru.
# Движок (imap/service.py) уже работает через абстракцию Credentials, поэтому
# добавление этого класса не потребует изменений в imap/.
#
# class OAuthCredentials(Credentials):
#     auth_method = "oauth"
#
#     def __init__(self, email, access_token):
#         super().__init__(email)
#         self.access_token = access_token
#
#     async def login(self, client):
#         xoauth2 = f"user={self.email}\x01auth=Bearer {self.access_token}\x01\x01"
#         return await client.xoauth2(self.email, xoauth2)
