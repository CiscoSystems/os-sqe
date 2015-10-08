def time_as_string():
    from pytz import timezone
    from datetime import datetime

    tz = timezone('Europe/Moscow')
    return datetime.now(tz).strftime('%d %m %Y %H:%M MSK')
