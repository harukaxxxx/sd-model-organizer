import json
import re
from urllib.parse import urlparse

import gradio as gr
import requests

from scripts.mo.environment import logger
from scripts.mo.ui_styled_html import alert_danger
from scripts.mo.ui_format import format_kilobytes


def _get_model_images(model_version_dict):
    result = []

    if model_version_dict.get('images') is not None:
        images = model_version_dict['images']
        for image in images:
            if image.get('url') is not None and image['url']:
                url = image['url']
                result.append((url, url))

    return result


def _create_model_dict(json_data):
    result = {
        'id': json_data['id'],
        'name': json_data['name'],
        'type': json_data['type'],  # TODO type parse
        'nsfw': json_data['nsfw'],
        'tags': json_data['tags'],  # TODO tags parse
    }

    if json_data.get('modelVersions') is not None:
        model_versions_dict = json_data['modelVersions']
        versions = []
        for version_data in model_versions_dict:
            version = {
                'id': version_data['id'],
                'name': version_data['name'],
                'updated_at': version_data['updatedAt'],
            }

            if version_data.get('images') is not None:
                images_data = version_data['images']
                images = []
                for image_data in images_data:
                    url = image_data['url']
                    images.append((url, url))
                version['images'] = images

            if version_data.get('files') is not None:
                files_data = version_data['files']
                files = []
                for file_data in files_data:
                    file = {
                        'id': file_data['id'],
                        'name': file_data['name'],
                        'sizeKB': file_data['sizeKB'],  # TODO parse display size
                        'type': file_data['type'],  # TODO parse model
                        'fp': file_data['metadata']['fp'], # TODO if exists
                        'size': file_data['metadata']['size'], # TODO if exists pruned | full
                        'format': file_data['metadata']['format'],
                        'display_name': f"{file_data['name']} - {format_kilobytes(file_data['sizeKB'])}",  # TODO format name
                        'download_url': file_data['downloadUrl'],
                        'is_primary': file_data['primary'] if file_data.get('primary') else False
                    }
                    files.append(file)
                version['files'] = files
            versions.append(version)
        result['versions'] = versions
    return result


def _on_import_url_clicked(url):
    pattern = r'^https:\/\/civitai\.com\/models\/\d+\/[a-zA-Z0-9-]+$'
    if not re.match(pattern, url) and not url.isdigit():
        return [
            gr.HTML.update(value=alert_danger('Invalid Url. The link should be a link to the model page like '
                                              'https://civitai.com/models/00000/model_name '
                                              'OR model id like 00000')),
            gr.Accordion.update(visible=False),
            gr.JSON.update(value='{}'),
            gr.Textbox.update(value='', visible=False),
            gr.Textbox.update(value='', visible=False),
            gr.Dropdown.update(value=None, choices=[], visible=False),
            gr.Textbox.update(value='', visible=False),
            gr.Accordion.update(visible=False),
            gr.Gallery.update(value=None, visible=False),
            gr.Dropdown(visible=False)
        ]

    if url.isdigit():
        model_id = url
    else:
        model_id = urlparse(url).path.split('/')[2]

    if not model_id.isdigit():
        return [
            gr.HTML.update(value=alert_danger(
                'Failed to parse model id. Check your input is valid civitai.com model url '
                'or model id.')),
            gr.Accordion.update(visible=False),
            gr.JSON.update(value='{}'),
            gr.Textbox.update(value='', visible=False),
            gr.Textbox.update(value='', visible=False),
            gr.Dropdown.update(value=None, choices=[], visible=False),
            gr.Textbox.update(value='', visible=False),
            gr.Accordion.update(visible=False),
            gr.Gallery.update(value=None, visible=False),
            gr.Dropdown(visible=False)
        ]

    url = f"https://civitai.com/api/v1/models/{model_id}"
    headers = {"Content-Type": "application/json"}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        data_dict = _create_model_dict(data)

        model_name = data['name'] if data.get('name') is not None and data['name'] else ''
        model_tags = []

        if data.get('tags') is not None:
            tags = data['tags']
            for tag in tags:
                model_tags.append(tag['name'])

        model_versions = []
        selected_version = None
        preview_images = None

        if data.get('modelVersions') is not None:
            model_versions_dict = data['modelVersions']
            for version in model_versions_dict:
                version_name = version['name']
                model_versions.append(version_name)
                if selected_version is None:
                    selected_version = version_name

            if len(model_versions) > 0:
                preview_images = _get_model_images(data['modelVersions'][0])

        if selected_version is not None:
            model_name += f' [{selected_version}]'

        return [
            gr.HTML.update(value=''),
            gr.Accordion.update(visible=True),
            gr.JSON.update(value=json.dumps(data)),
            gr.Textbox.update(value=model_name, visible=True),
            gr.Textbox.update(value=', '.join(model_tags), visible=True),
            gr.Dropdown.update(value=selected_version, choices=model_versions, visible=True),
            gr.Textbox.update(value=preview_images[0][0], visible=True),
            gr.Accordion.update(visible=True),
            gr.Gallery.update(value=preview_images, visible=True),
            gr.Dropdown(visible=True)
        ]
    else:
        return [
            gr.HTML.update(value=alert_danger(f'Request failed with status code: {response.status_code}')),
            gr.Accordion.update(visible=False, open=False),
            gr.JSON.update(value='{}'),
            gr.Textbox.update(value='', visible=False),
            gr.Textbox.update(value='', visible=False),
            gr.Dropdown.update(value=None, choices=[], visible=False),
            gr.Textbox.update(value='', visible=False),
            gr.Accordion.update(visible=False),
            gr.Gallery.update(value=None, visible=False),
            gr.Dropdown(visible=False)
        ]


def _on_preview_selected(selected_preview):
    logger.debug(f'selected preview: {selected_preview}')


def civitai_import_ui_block():
    import_url_textbox = gr.Textbox('https://civitai.com/models/4468/counterfeit-v30',
                                    label='civitai.com model url')
    with gr.Row():
        gr.Markdown()
        gr.Markdown()
        gr.Markdown()
        import_url_button = gr.Button('Import URL')

    import_result_html = gr.HTML('')
    with gr.Accordion(label='JSON Response', visible=False, open=False) as json_accordion:
        import_result_json = gr.JSON()

    name_widget = gr.Textbox(label='Name', visible=False, interactive=True)
    tags_widget = gr.Textbox(label='Tags', visible=False, interactive=True)
    model_version_dropdown = gr.Dropdown(label='Model Version', visible=False, interactive=True)
    preview_url_widget = gr.Textbox(label='Preview image URL. Or copy-paste another preview url from the'
                                          ' \"Image Previews\" gallery below', visible=False, interactive=True)

    with gr.Accordion(label='Image previews', visible=False, open=False) as preview_accordion:
        preview_gallery = gr.Gallery(elem_id='preview_gallery', visible=False).style(grid=10, height="auto")

    files_dropdown = gr.Dropdown(label='Model Files:', visible=False)

    import_url_button.click(_on_import_url_clicked,
                            inputs=import_url_textbox,
                            outputs=[import_result_html,
                                     json_accordion,
                                     import_result_json,
                                     name_widget,
                                     tags_widget,
                                     model_version_dropdown,
                                     preview_url_widget,
                                     preview_accordion,
                                     preview_gallery,
                                     files_dropdown
                                     ])

    preview_gallery.select(fn=_on_preview_selected, inputs=preview_gallery)