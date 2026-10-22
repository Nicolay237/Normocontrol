# -*- coding: utf-8 -*-
"""
Служебные письма (код подтверждения почты, сброс пароля) через SMTP почтового сервиса.

Напрямую с VPS письма не отправляем: у IP сервера нет почтовой репутации, письма уйдут в спам,
а порт 25 хостинг закрывает. Почтовый сервис (почта рег.ру на домене) отправляет от своего имени.

  SMTP_HOST      mail.hosting.reg.ru
  SMTP_PORT      465 (SSL) или 587 (STARTTLS)
  SMTP_USER      noreply@normocontrol.site — полный адрес ящика
  SMTP_PASSWORD  пароль от ящика
  MAIL_FROM      адрес отправителя (по умолчанию SMTP_USER)

Пока SMTP не настроен, enabled() — False: регистрация работает без подтверждения почты.
Для разработки: SMTP_HOST=console — письма не отправляются, а печатаются в журнал сервера.
"""

import os
import ssl
import smtplib
import logging
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

log = logging.getLogger("normocontrol.mail")


def _cfg():
    env = lambda k, d="": os.environ.get(k, d).strip()
    user = env("SMTP_USER")
    return {"host": env("SMTP_HOST"), "port": int(env("SMTP_PORT", "465") or 465), "user": user,
            "password": env("SMTP_PASSWORD"), "from": env("MAIL_FROM") or user}


def enabled():
    c = _cfg()
    return c["host"] == "console" or bool(c["host"] and c["user"] and c["password"])


def send(to, subject, text):
    """Отправляет письмо. Ошибку SMTP пробрасывает — вызывающий решает, что сказать пользователю."""
    c = _cfg()
    if c["host"] == "console":
        log.warning("письмо для %s: %s\n%s", to, subject, text)
        return
    msg = EmailMessage()
    msg["From"] = formataddr(("Нормоконтроль", c["from"]))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=c["from"].split("@")[-1])
    msg.set_content(text)
    ctx = ssl.create_default_context()
    if c["port"] == 465:
        with smtplib.SMTP_SSL(c["host"], c["port"], context=ctx, timeout=20) as s:
            s.login(c["user"], c["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(c["host"], c["port"], timeout=20) as s:
            s.starttls(context=ctx)
            s.login(c["user"], c["password"])
            s.send_message(msg)
    log.info("письмо «%s» отправлено", subject)


def code_letter(kind, code, site):
    """Текст письма с кодом: kind — verify (подтверждение почты) или reset (сброс пароля)."""
    if kind == "verify":
        subject = f"Код подтверждения: {code}"
        intro = "Вы зарегистрировались на сайте «Нормоконтроль». Чтобы подтвердить почту, введите код:"
    else:
        subject = f"Сброс пароля: код {code}"
        intro = "Кто-то (возможно, вы) запросил сброс пароля на сайте «Нормоконтроль». Код для сброса:"
    text = (f"Здравствуйте!\n\n{intro}\n\n    {code}\n\nКод действует 30 минут.\n\n"
            f"Если вы ничего не запрашивали, просто проигнорируйте это письмо.\n\n"
            f"— Нормоконтроль, {site}\n")
    return subject, text
