def safe_cut(text, limit=3500):
    return text[:limit] if text else ""

def format_msg(msg_dict):
    sender_name = msg_dict['sender_name']
    sender_email = msg_dict['sender_email']
    subject = msg_dict['subject']
    text = msg_dict['text']
    has_att = msg_dict['has_att']
    message = (
        f'📨 Новое письмо!\n'
        f'👻 Имя отправителя: {sender_name}\n'
        f'📧 Почта отправителя: {sender_email}\n'
        f'📎 Прикрепленные файлы: {"есть" if has_att else "нет"}\n\n'
        f'🙉 Тема: {subject}\n'
        f'💬 Текст:\n\n'
        f'{safe_cut(text)}\n\n'
    )
    return safe_cut(message, 4000)