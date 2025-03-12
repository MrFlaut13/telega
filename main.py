import asyncio
from datetime import datetime, timedelta
from getpass import getpass
from telethon import TelegramClient, functions, types, utils
from telethon.errors import SessionPasswordNeededError, ChannelInvalidError
from colorama import Fore, Style, init

init(autoreset=True)

MAX_SCHEDULED_MESSAGES = 100


async def load_or_create_session():
    """Выбор между существующей и новой сессией"""
    try:
        client = TelegramClient('tg_scheduler', 0, '')
        if client.session.exists():
            choice = input(f"{Fore.YELLOW}Найдена сохраненная сессия. Использовать её? (y/n): ")
            if choice.lower() == 'y':
                await client.connect()
                return client
        return None
    except Exception as e:
        print(f"{Fore.RED}🚫 Ошибка при загрузке сессии: {e}")
        return None


async def get_scheduled_messages_count(client, entity):
    """Получить количество отложенных сообщений"""
    try:
        scheduled = await client.get_scheduled_messages(entity)
        return len(scheduled)
    except Exception as e:
        print(f"{Fore.YELLOW}⚠ Предупреждение: {e}")
        return 0


async def choose_chat(client):
    """Выбор чата и темы (подчата)"""
    try:
        dialogs = await client.get_dialogs()
        print(f"\n{Fore.CYAN}🌀 Доступные чаты:")
        for i, d in enumerate(dialogs, 1):
            print(f"{Fore.GREEN}[{i}]{Style.RESET_ALL} {d.name}")

        while True:
            try:
                choice = int(input(f"\n{Fore.BLUE}❔ Выберите чат (1-{len(dialogs)}): "))
                entity = dialogs[choice - 1].entity
                break
            except (ValueError, IndexError):
                print(f"{Fore.RED}🚫 Некорректный выбор!")

        if isinstance(entity, types.Channel) and entity.forum:
            try:
                input_channel = utils.get_input_channel(entity)
                result = await client(
                    functions.channels.GetForumTopicsRequest(
                        channel=input_channel,
                        offset_date=datetime.now(),
                        offset_id=0,
                        offset_topic=0,
                        limit=100
                    )
                )
                topics = result.topics
                print(f"\n{Fore.CYAN}📚 Доступные темы:")
                for i, topic in enumerate(topics, 1):
                    print(f"{Fore.GREEN}[{i}]{Style.RESET_ALL} {topic.title}")

                while True:
                    try:
                        topic_choice = int(input(f"{Fore.BLUE}❔ Выберите тему (1-{len(topics)}): "))
                        topic_id = topics[topic_choice - 1].id
                        return entity, topic_id
                    except (ValueError, IndexError):
                        print(f"{Fore.RED}🚫 Некорректный выбор!")
            except Exception as e:
                print(f"{Fore.RED}🚫 Ошибка при получении тем: {e}")
                return entity, None
        else:
            return entity, None

    except Exception as e:
        print(f"{Fore.RED}🚫 Критическая ошибка: {e}")
        return None, None


async def main():
    print(f"\n{Fore.MAGENTA}⚡ TG Scheduler ULTIMATE v8.0{Style.RESET_ALL}")

    client = None
    try:
        client = await load_or_create_session()
        if not client:
            api_id = int(input(f"{Fore.BLUE}Введите API ID: "))
            api_hash = input(f"{Fore.BLUE}Введите API Hash: ")
            client = TelegramClient('tg_scheduler', api_id, api_hash)
            await client.start(
                phone=lambda: input(f"\n{Fore.BLUE}📱 Введите номер телефона (+7...): "),
                code_callback=lambda: input(f"{Fore.BLUE}🔑 Введите код из Telegram: "),
                password=lambda: getpass(f"{Fore.BLUE}🔒 Введите пароль 2FA: "),
                max_attempts=3
            )

        if not await client.is_user_authorized():
            print(f"{Fore.RED}🚫 Авторизация не удалась!")
            return

        # Выбор чата
        entity, topic_id = await choose_chat(client)
        if entity is None:
            print(f"{Fore.RED}🚫 Чат не выбран!")
            return

        # Проверка лимита
        scheduled_count = await get_scheduled_messages_count(client, entity)
        available_slots = MAX_SCHEDULED_MESSAGES - scheduled_count
        if available_slots <= 0:
            print(f"{Fore.RED}🚫 Достигнут лимит в {MAX_SCHEDULED_MESSAGES} сообщений!")
            return

        # Ввод сообщений
        schedule = []
        print(f"\n{Fore.CYAN}📝 Формат: текст[:количество] (пример: новость:3)")
        print(f"{Fore.YELLOW}❕ Доступно слотов: {available_slots}")

        while available_slots > 0:
            entry = input(f"{Fore.BLUE}➡ Введите сообщение или 'done': ").strip()
            if entry.lower() == 'done':
                if not schedule:
                    print(f"{Fore.RED}🚫 Нужно ввести хотя бы одно сообщение!")
                    continue
                break

            # Парсинг ввода
            if ':' in entry:
                msg_part, _, count_part = entry.partition(':')
                msg = msg_part.strip()
                try:
                    count = min(int(count_part), available_slots)
                    if count <= 0:
                        raise ValueError
                except ValueError:
                    print(f"{Fore.RED}🚫 Некорректное количество!")
                    continue
            else:
                msg = entry.strip()
                count = 1

            # Добавление сообщений
            for _ in range(count):
                if available_slots <= 0:
                    break
                schedule.append(msg)
                available_slots -= 1

            print(f"{Fore.YELLOW}♻ Осталось слотов: {available_slots}")

        # Ввод интервала
        while True:
            interval_input = input(f"{Fore.BLUE}⏱ Интервал между сообщениями (минут): ")
            try:
                interval = int(interval_input)
                if interval <= 0:
                    raise ValueError
                break
            except ValueError:
                print(f"{Fore.RED}🚫 Введите целое число больше 0!")

        # Отправка сообщений
        start_time = datetime.now()
        for i, msg in enumerate(schedule):
            try:
                send_time = start_time + timedelta(minutes=i * interval)
                await client.send_message(
                    entity=entity,
                    message=msg,
                    schedule=send_time,
                    reply_to=topic_id if topic_id else None
                )
                print(f"{Fore.GREEN}✓ Сообщение {i + 1} запланировано на {send_time.strftime('%H:%M')}")
            except Exception as e:
                print(f"{Fore.RED}🚫 Ошибка при отправке сообщения {i + 1}: {e}")

    except KeyboardInterrupt:
        print(f"\n{Fore.RED}🚫 Прервано пользователем!")
    except Exception as e:
        print(f"\n{Fore.RED}💥 Критическая ошибка: {e}")
    finally:
        if client:
            await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())