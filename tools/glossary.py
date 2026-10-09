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
    "Hostile list": ("Feindliste", "Список врагов", "敌对列表"),
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
    "No contacts in aa-contacts yet, so missing from this list:": (
        "Noch keine Kontakte in aa-contacts, daher fehlen in dieser Liste:",
        "В aa-contacts ещё нет контактов, поэтому в этом списке отсутствуют:",
        "aa-contacts 中尚无联系人，因此此列表中缺少：",
    ),
    "Contacts with a standing below %(threshold)s": (
        "Kontakte mit einem Standing unter %(threshold)s",
        "Контакты со стендингом ниже %(threshold)s",
        "声望低于 %(threshold)s 的联系人",
    ),
    "Name": ("Name", "Название", "名称"),
    "Type": ("Typ", "Тип", "类型"),
    "Standing": ("Standing", "Стендинг", "声望"),
    "Sources": ("Quellen", "Источники", "来源"),
    "No hostile contacts.": ("Keine feindlichen Kontakte.", "Нет враждебных контактов.", "没有敌对联系人。"),
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
    "Settings saved.": ("Einstellungen gespeichert.", "Настройки сохранены.", "设置已保存。"),
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
