import json
import re
from datetime import datetime
import mwclient

config = json.load(open('config.json', 'r', encoding='utf-8'))
site = mwclient.Site(config['site'])
site.login(config['bot_username'], config['bot_password'])
template_name = 'Template:TalkpageCountdown'
template_regex = re.compile(r'\{\{TalkpageCountdown\s*?\|(.+?\||)target-time=([\d\-:TZ+]{8,25}).*?\}\}')
log_page_name = 'User:Tiger-bot/watchlist/1'


def get_transclude_in() -> list[str]:
    """
    Get list of title of pages containing the specified template.
    :return:
    """
    query_data = {
        "format": "json",
        "prop": "transcludedin",
        "titles": template_name,
        "utf8": 1,
        "formatversion": "2",
        "tiprop": "title",
        "tishow": "!redirect",
        "tilimit": "max"
    }
    pages = []
    api_result = site.api('query', **query_data)

    if 'transcludedin' in api_result['query']['pages'][0]:
        pages = api_result['query']['pages'][0]['transcludedin']
    while 'continue' in api_result:
        continue_token = api_result['continue']['ticontinue']
        query_data['ticontinue'] = continue_token
        api_result = site.api('query', **query_data)
        pages.extend(api_result['query']['pages'][0]['transcludedin'])

    output = [item['title'].replace(' ', '_') for item in pages if item['title'] != template_name]

    return output


def get_sections_with_template(page_title: str) -> list[tuple[str, str]]:
    """
    Get title of sections which have the specified template in it. Only top level sections are considered.
    :param page_title: The title to work on
    :return: List of top level sections containing the template
    """
    # Get list of all sections
    query_sections_data = {
        "format": "json",
        "page": page_title,
        "prop": "sections",
        "utf8": 1,
        "formatversion": "2"
    }
    section_result = site.api('parse', **query_sections_data)
    sections = section_result['parse']['sections']
    section_idx = [item['index'] for item in sections if item['fromtitle'] == page_title and item['toclevel'] == 1]

    # From each section, find if there's target template in it
    section_with_template: list[tuple[str, str]] = []   # (section title, target time)
    query_section_template_data = {
        "format": "json",
        "page": page_title,
        "prop": "templates|wikitext|sections",
        # "section": "16",
        "utf8": 1,
        "formatversion": "2"
    }
    for idx in section_idx:
        query_section_template_data['section'] = idx
        template_result = site.api('parse', **query_section_template_data)
        for template in template_result['parse']['templates']:
            if template['title'] == template_name:
                # Target template found
                template_search = template_regex.search(template_result['parse']['wikitext'])
                target_time = template_search.groups()[1]
                # (section index, section title, target time)
                section_with_template.append((template_result['parse']['sections']['line'], target_time))

    return section_with_template


def main():
    page_with_template = get_transclude_in()
    sections_with_template: dict[str, list[tuple[str, str]]] = {}   # {page title: (section title, target time)}

    unexpired_log_text = '== 未到期 ==\n'
    expired_log_text = '== 已到期 ==\n'

    for page_title in page_with_template:
        sections = get_sections_with_template(page_title)   # (section title, target time)
        sections_with_template[page_title] = sections
        for section in sections:
            if datetime.utcnow() < datetime.fromisoformat(section[1]):
                unexpired_log_text += f'* [[{page_title}#{section[0]}]] - {section[1]}\n'
            else:
                expired_log_text +=f'* [[{page_title}#{section[0]}]] - {section[1]}\n'

    log_text = f'{expired_log_text}\n\n{unexpired_log_text}\n'

    log_page = site.pages[log_page_name]
    log_page.edit(log_text, f'更新{template_name}使用情况')


if __name__ == '__main__':
    main()
