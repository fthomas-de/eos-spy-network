"""Translations of every eos_spy_network message: (de, ru, zh_Hans).

The German, Russian and Simplified Chinese translations are machine-generated and may be inaccurate.
Checked for sense, not by a native speaker - a correction goes here.

The source of truth for the catalogues - tools/translate.py writes these into
the .po files and refuses to run while a message is missing here. Add a new
message here, never in a .po file: the next run would overwrite a hand edit.

EVE jargon stays English in every language: Corporation, Alliance, Main,
Character, Faction, ISK. A term Alliance Auth translates itself (Alliance,
Corporation) needs the "EVE jargon" context in the code as well, or AA's
catalogue wins and the English never shows.

A short word Alliance Auth translates differently ("Name", "Type", "Status")
needs the "eos-spy-network" context in the code; the translation test in
tests/test_translations.py names every such clash.

Plural forms: de 2, ru 3, zh_Hans 1.
"""

LANGUAGES = ("de", "ru", "zh_Hans")

PLURAL_FORMS = {
    "de": "nplurals=2; plural=(n != 1);",
    "ru": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    "zh_Hans": "nplurals=1; plural=0;",
}

TRANSLATIONS = {
    "Spy Network": ("Spy Network", "Spy Network", "Spy Network"),
    # EVE jargon, with the "EVE jargon" context in the code: English everywhere
    "Character": ("Character", "Character", "Character"),
    "Corporation": ("Corporation", "Corporation", "Corporation"),
    "Alliance": ("Alliance", "Alliance", "Alliance"),
    "Faction": ("Faction", "Faction", "Faction"),
    "The Alliance whose members are checked.": (
        "Die Alliance, deren Mitglieder geprüft werden.",
        "Alliance, участники которого проверяются.",
        "要检查其成员的 Alliance。",
    ),
    "Hostile below standing": (
        "Feindlich unter Standing",
        "Враждебен при стендинге ниже",
        "低于此声望即为敌对",
    ),
    "A contact of a ticked source counts as hostile when its standing is below this value.": (
        "Ein Kontakt einer angehakten Quelle gilt als feindlich, wenn sein Standing unter diesem Wert liegt.",
        "Контакт отмеченного источника считается враждебным, если его стендинг ниже этого значения.",
        "已勾选来源的联系人，其声望低于此值时视为敌对。",
    ),
    "Configuration": ("Konfiguration", "Конфигурация", "配置"),
    "Settings": ("Einstellungen", "Настройки", "设置"),
    "aa-contacts is not installed: the hostile list is made from its contacts.": (
        "aa-contacts ist nicht installiert: Die Feindliste entsteht aus dessen Kontakten.",
        "aa-contacts не установлен: список врагов строится из его контактов.",
        "未安装 aa-contacts：敌对列表由其联系人生成。",
    ),
    "No Alliance is configured yet.": (
        "Es ist noch keine Alliance eingestellt.",
        "Alliance ещё не настроен.",
        "尚未配置 Alliance。",
    ),
    "Open the settings": ("Einstellungen öffnen", "Открыть настройки", "打开设置"),
    "No contact source is ticked, so nothing counts as hostile.": (
        "Keine Kontaktquelle ist angehakt, daher gilt nichts als feindlich.",
        "Ни один источник контактов не отмечен, поэтому ничто не считается враждебным.",
        "未勾选任何联系人来源，因此没有任何对象被视为敌对。",
    ),
    "Name": ("Name", "Название", "名称"),
    "Type": ("Typ", "Тип", "类型"),
    "Contact sources": ("Kontaktquellen", "Источники контактов", "联系人来源"),
    "Tick whose contacts make up the hostile list. The contacts come from aa-contacts: a source needs a token there, and aa-contacts' own task keeps them up to date.": (
        "Hake an, wessen Kontakte die Feindliste bilden. Die Kontakte kommen aus aa-contacts: Eine Quelle braucht dort einen Token, und der eigene Task von aa-contacts hält sie aktuell.",
        "Отметьте, чьи контакты составляют список врагов. Контакты берутся из aa-contacts: источнику нужен там токен, а собственная задача aa-contacts поддерживает их в актуальном состоянии.",
        "勾选其联系人构成敌对列表的来源。联系人来自 aa-contacts：来源需要在其中拥有令牌，aa-contacts 自己的任务会保持其最新。",
    ),
    "Open aa-contacts": ("aa-contacts öffnen", "Открыть aa-contacts", "打开 aa-contacts"),
    "Ticked": ("Angehakt", "Отмечено", "已勾选"),
    "Token in aa-contacts": ("Token in aa-contacts", "Токен в aa-contacts", "aa-contacts 中的令牌"),
    "Contacts as of": ("Kontakte vom", "Контакты на", "联系人截至"),
    "Contacts": ("Kontakte", "Контакты", "联系人"),
    "Hostile": ("Feindlich", "Враждебные", "敌对"),
    "Not in the Alliance": ("Nicht in der Alliance", "Не в Alliance", "不在 Alliance 中"),
    "Yes": ("Ja", "Да", "是"),
    "No": ("Nein", "Нет", "否"),
    "Not read yet": ("Noch nicht gelesen", "Ещё не прочитано", "尚未读取"),
    "Choose an Alliance first: its Corporations are listed here once it is saved.": (
        "Wähle zuerst eine Alliance: Ihre Corporations erscheinen hier, sobald sie gespeichert ist.",
        "Сначала выберите Alliance: её Corporation появятся здесь после сохранения.",
        "请先选择 Alliance：保存后，其 Corporation 会列在这里。",
    ),
    "Save": ("Speichern", "Сохранить", "保存"),
    # EVE jargon, English everywhere. The plurals carry the "eos-spy-network"
    # context: under "EVE jargon" Alliance Auth shows the singular in ru and zh_Hans
    "Main": ("Main", "Main", "Main"),
    "Mains": ("Mains", "Mains", "Mains"),
    "Characters": ("Characters", "Characters", "Characters"),
    "Suspects": ("Verdächtige", "Подозреваемые", "嫌疑人"),
    "Hostile membership": ("Feindliche Mitgliedschaft", "Членство у врагов", "敌对成员身份"),
    "Frequent Corporation changes": (
        "Häufige Corporation-Wechsel",
        "Частая смена Corporation",
        "频繁更换 Corporation",
    ),
    "Friendly to hostiles": ("Freundlich zu Feinden", "Дружелюбен к врагам", "对敌对方友好"),
    "Mails with hostiles": ("Mails mit Feinden", "Почта с врагами", "与敌对方的邮件"),
    "ISK with hostiles": ("ISK mit Feinden", "ISK с врагами", "与敌对方的 ISK"),
    "Contracts with hostiles": ("Contracts mit Feinden", "Контракты с врагами", "与敌对方的合同"),
    "A character is or was in a hostile Corporation or Alliance.": (
        "Ein Character ist oder war in einer feindlichen Corporation oder Alliance.",
        "Character состоит или состоял во враждебной Corporation или Alliance.",
        "某个 Character 现在或曾经在敌对的 Corporation 或 Alliance 中。",
    ),
    "A character joined many Corporations within the last 365 days.": (
        "Ein Character ist in den letzten 365 Tagen vielen Corporations beigetreten.",
        "Character вступил во многие Corporation за последние 365 дней.",
        "某个 Character 在过去 365 天内加入了许多 Corporation。",
    ),
    "A character's own contacts hold a hostile with a positive standing or on the watch list.": (
        "Die eigenen Kontakte eines Characters führen einen Feind mit positivem Standing oder auf der Beobachtungsliste.",
        "В собственных контактах Character есть враг с положительным стендингом или в списке наблюдения.",
        "某个 Character 自己的联系人中有敌对方，声望为正或在关注列表中。",
    ),
    "Mails from or to hostiles.": ("Mails von oder an Feinde.", "Письма от врагов или к ним.", "来自或发往敌对方的邮件。"),
    "Wallet journal entries with hostiles.": (
        "Wallet-Journal-Einträge mit Feinden.",
        "Записи журнала кошелька с врагами.",
        "与敌对方的钱包日志条目。",
    ),
    "Contracts with hostiles.": ("Contracts mit Feinden.", "Контракты с врагами.", "与敌对方的合同。"),
    "Corporation changes per year": (
        "Corporation-Wechsel pro Jahr",
        "Смен Corporation в год",
        "每年更换 Corporation 次数",
    ),
    "A character that joined this many Corporations within the last 365 days gets a marker.": (
        "Ein Character, der in den letzten 365 Tagen so vielen Corporations beigetreten ist, bekommt einen Marker.",
        "Character, вступивший в столько Corporation за последние 365 дней, получает маркер.",
        "在过去 365 天内加入这么多 Corporation 的 Character 会被标记。",
    ),
    "Mains with markers": ("Mains mit Markern", "Mains с маркерами", "有标记的 Mains"),
    "Markers": ("Marker", "Маркеры", "标记"),
    "No markers.": ("Keine Marker.", "Нет маркеров.", "没有标记。"),
    # Alliance Auth's own wording, which wins the msgid anyway
    "View details": ("Details anzeigen", "Подробнее", "查看详情"),
    "Back": ("Zurück", "Назад", "返回"),
    "Auth knows no Corporation of this Alliance.": (
        "Auth kennt keine Corporation dieser Alliance.",
        "Auth не знает ни одной Corporation этого Alliance.",
        "Auth 不知道此 Alliance 的任何 Corporation。",
    ),
    "aa-contacts is not installed: the hostiles are made from its contacts.": (
        "aa-contacts ist nicht installiert: Die Feinde entstehen aus dessen Kontakten.",
        "aa-contacts не установлен: враги определяются по его контактам.",
        "未安装 aa-contacts：敌对方由其联系人生成。",
    ),
    "No contacts in aa-contacts yet, so these sources add no hostiles:": (
        "Noch keine Kontakte in aa-contacts, daher liefern diese Quellen keine Feinde:",
        "В aa-contacts ещё нет контактов, поэтому эти источники не дают врагов:",
        "aa-contacts 中尚无联系人，因此这些来源不提供敌对方：",
    ),
    "corptools is not installed: only the current Corporation and Alliance of the characters are checked.": (
        "corptools ist nicht installiert: Geprüft werden nur die aktuelle Corporation und Alliance der Characters.",
        "corptools не установлен: проверяются только текущие Corporation и Alliance каждого Character.",
        "未安装 corptools：只检查各 Character 当前的 Corporation 和 Alliance。",
    ),
    # network pages
    "Network": ("Network", "Сеть", "关系网"),
    "Hide Corporations without markers": (
        "Corporations ohne Marker ausblenden",
        "Скрыть Corporations без маркеров",
        "隐藏无标记的 Corporations",
    ),
    "Mains with connections": ("Mains mit Verbindungen", "Mains со связями", "有关联的 Mains"),
    "At least two characters of the account exchanged ISK with the same character outside the Alliance.": (
        "Mindestens zwei Characters des Accounts haben ISK mit demselben Character außerhalb der Alliance getauscht.",
        "Как минимум два Character аккаунта обменивались ISK с одним и тем же Character вне Alliance.",
        "该账号至少有两个 Character 与 Alliance 外的同一 Character 有过 ISK 往来。",
    ),
    "Shared payment partner": ("Gemeinsamer Zahlungspartner", "Общий платёжный партнёр", "共同付款对象"),
    "Player trading with characters outside the Alliance.": (
        "Player Trading mit Characters außerhalb der Alliance.",
        "Player trading с Character вне Alliance.",
        "与 Alliance 外 Character 的 Player trading。",
    ),
    "Player trading": ("Player Trading", "Player trading", "Player trading"),
    "No connections outside the Alliance.": (
        "Keine Verbindungen außerhalb der Alliance.",
        "Нет связей вне Alliance.",
        "没有与 Alliance 外的关联。",
    ),
    "Payments": ("Zahlungen", "Платежи", "付款"),
    "Alt": ("Alt", "Alt", "Alt"),
    "Counterpart": ("Gegenüber", "Контрагент", "对方"),
    # recalculation and its footer
    "Last calculation %(seconds)s s, %(queries)s queries (%(query_seconds)s s)": (
        "Letzte Berechnung %(seconds)s s, %(queries)s Abfragen (%(query_seconds)s s)",
        "Последний расчёт %(seconds)s с, %(queries)s запросов (%(query_seconds)s с)",
        "上次计算 %(seconds)s 秒，%(queries)s 次查询（%(query_seconds)s 秒）",
    ),
    "%(corporations)s Corporations, %(accounts)s accounts, %(characters)s characters": (
        "%(corporations)s Corporations, %(accounts)s Accounts, %(characters)s Characters",
        "Corporations: %(corporations)s, аккаунтов: %(accounts)s, Characters: %(characters)s",
        "%(corporations)s 个 Corporations，%(accounts)s 个账号，%(characters)s 个 Characters",
    ),
    "%(entries)s wallet entries": (
        "%(entries)s Wallet-Einträge",
        "записей кошелька: %(entries)s",
        "%(entries)s 条钱包记录",
    ),
    "%(kilobytes)s KB stored": ("%(kilobytes)s KB gespeichert", "сохранено %(kilobytes)s КБ", "已存储 %(kilobytes)s KB"),
    "page %(milliseconds)s ms": ("Seite %(milliseconds)s ms", "страница %(milliseconds)s мс", "页面 %(milliseconds)s 毫秒"),
    "Calculated %(built_at)s": ("Berechnet %(built_at)s", "Рассчитано %(built_at)s", "计算于 %(built_at)s"),
    "Not calculated yet.": ("Noch nicht berechnet.", "Ещё не рассчитано.", "尚未计算。"),
    "Recalculate": ("Neu berechnen", "Пересчитать", "重新计算"),
    "The markers and connections are being recalculated.": (
        "Marker und Verbindungen werden neu berechnet.",
        "Маркеры и связи пересчитываются.",
        "正在重新计算标记和关联。",
    ),
    "Recalculating": ("Neuberechnung läuft", "Идёт пересчёт", "正在重新计算"),
    # the steps of the progress bar
    "Waiting for the task queue": ("Warte auf die Task-Queue", "Ожидание очереди задач", "等待任务队列"),
    "Reading the hostile contacts": ("Lese die feindlichen Kontakte", "Чтение враждебных контактов", "读取敌对联系人"),
    "Checking memberships": ("Prüfe Mitgliedschaften", "Проверка членства", "检查成员关系"),
    "Checking Corporation histories": (
        "Prüfe Corporation-Historien",
        "Проверка истории Corporation",
        "检查 Corporation 历史",
    ),
    "Checking contacts": ("Prüfe Kontakte", "Проверка контактов", "检查联系人"),
    "Checking mails": ("Prüfe Mails", "Проверка писем", "检查邮件"),
    "Checking wallet journals": ("Prüfe Wallet-Journale", "Проверка журналов кошелька", "检查钱包日志"),
    "Checking contracts": ("Prüfe Verträge", "Проверка контрактов", "检查合同"),
    "Finding connections outside the Alliance": (
        "Suche Verbindungen außerhalb der Alliance",
        "Поиск связей за пределами Alliance",
        "查找 Alliance 外部的关联",
    ),
    "Looking up Corporations and Alliances": (
        "Ermittle Corporations und Alliances",
        "Определение Corporation и Alliance",
        "查询 Corporation 和 Alliance",
    ),
    "Saving the result": ("Speichere das Ergebnis", "Сохранение результата", "保存结果"),
    "Affiliations": ("Zugehörigkeiten", "Принадлежность", "所属关系"),
    # network page
    "Hide Corporations without connections": (
        "Corporations ohne Verbindungen ausblenden",
        "Скрыть Corporation без связей",
        "隐藏没有关联的 Corporation",
    ),
    "The partner, its Corporation or its Alliance is a hostile contact.": (
        "Der Partner, seine Corporation oder seine Alliance ist ein feindlicher Kontakt.",
        "Партнёр, его Corporation или его Alliance — враждебный контакт.",
        "该对象、其 Corporation 或其 Alliance 是敌对联系人。",
    ),
    "Hostile partner": ("Feindlicher Partner", "Враждебный партнёр", "敌对对象"),
    "Click a main to see its connections.": (
        "Klicke auf einen Main, um seine Verbindungen zu sehen.",
        "Нажмите на Main, чтобы увидеть его связи.",
        "点击一个 Main 查看其关联。",
    ),
    "Standing": ("Standing", "Standing", "Standing"),
    "unknown": ("unbekannt", "неизвестно", "未知"),
    "Partner outside the Alliance": (
        "Partner außerhalb der Alliance",
        "Партнёр за пределами Alliance",
        "Alliance 外部的对象",
    ),
    "Hostile Corporation": ("Feindliche Corporation", "Враждебная Corporation", "敌对 Corporation"),
    "Hostile Alliance": ("Feindliche Alliance", "Враждебный Alliance", "敌对 Alliance"),
    "The recalculation could not be started: the task queue is not reachable.": (
        "Die Neuberechnung konnte nicht gestartet werden: Die Task-Queue ist nicht erreichbar.",
        "Не удалось запустить пересчёт: очередь задач недоступна.",
        "无法开始重新计算：任务队列不可达。",
    ),
    "Settings saved. The markers and connections are being recalculated.": (
        "Einstellungen gespeichert. Marker und Verbindungen werden neu berechnet.",
        "Настройки сохранены. Маркеры и связи пересчитываются.",
        "设置已保存。正在重新计算标记和关联。",
    ),
    "Settings saved, but the task queue is not reachable: recalculate once it is back.": (
        "Einstellungen gespeichert, aber die Task-Queue ist nicht erreichbar: Neu berechnen, sobald sie wieder da ist.",
        "Настройки сохранены, но очередь задач недоступна: пересчитайте, когда она снова заработает.",
        "设置已保存，但任务队列不可达：恢复后请重新计算。",
    ),
}

PLURALS = {}


def problems():
    """What is malformed in the entries above, as readable lines.

    tools/translate.py stops on any of these before it touches a catalogue,
    and the normal test suite runs the same check: a tuple one language short
    would otherwise end in an IndexError deep inside the fill, and a plural
    with the wrong number of forms or a lost placeholder would only show when
    a page renders it.
    """
    import re

    placeholder = re.compile(r"%\([a-z_]+\)s|\{[^}]*\}")
    found = []

    def check(msgid, text, where):
        if not isinstance(text, str) or not text:
            found.append(f"{where}: {msgid!r} has an empty or non-text translation")
        elif sorted(placeholder.findall(text)) != sorted(placeholder.findall(msgid)):
            found.append(f"{where}: {msgid!r} has other placeholders than the English")

    for msgid, values in TRANSLATIONS.items():
        if not isinstance(values, tuple) or len(values) != len(LANGUAGES):
            found.append(f"{msgid!r} needs one translation per language {LANGUAGES}")
            continue
        for language, text in zip(LANGUAGES, values):
            check(msgid, text, language)

    for msgid, values in PLURALS.items():
        if not isinstance(values, tuple) or len(values) != len(LANGUAGES):
            found.append(f"{msgid!r} needs one list of plural forms per language {LANGUAGES}")
            continue
        for language, forms in zip(LANGUAGES, values):
            wanted = int(re.search(r"nplurals=(\d+)", PLURAL_FORMS[language]).group(1))
            if not isinstance(forms, list) or len(forms) != wanted:
                found.append(f"{language}: {msgid!r} needs {wanted} plural forms")
                continue
            for text in forms:
                check(msgid, text, language)

    return found
