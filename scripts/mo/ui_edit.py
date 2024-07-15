import html
import json
import os.path
import time

import gradio as gr

import scripts.mo.ui_styled_html as styled
from scripts.mo.data.storage import map_dict_to_record
from scripts.mo.dl.download_manager import DownloadManager, calculate_sha256
from scripts.mo.environment import env, logger
from scripts.mo.models import Record, ModelType
from scripts.mo.ui_navigation import generate_ui_token
from scripts.mo.utils import is_blank, is_valid_filename, is_valid_url, get_model_files_in_dir, find_preview_file


def is_directory_path_valid(path):
    if os.path.exists(path):
        return not os.path.isfile(path) and os.path.isdir(path)
    else:
        try:
            os.makedirs(path)
            return True
        except Exception as ex:
            logger.warning(ex)
            return False

def is_filename_with_extension(download_filename):
    filename, extension = os.path.splitext(download_filename)
    return bool(filename and extension)

def _on_description_output_changed(record_data, name: str, model_type_value: str, download_url: str, backup_url: str, url: str,
                                   download_path: str, download_filename: str, rename_filename: bool, download_subdir: str, preview_url: str,
                                   description_output: str, positive_prompts: str, negative_prompts: str,
                                   groups, back_token: str, sha256_state, location, current_location, promptweight: float):
    errors = []
    if is_blank(name):
        errors.append('Name field is empty.')

    if not is_blank(model_type_value):
        model_type = ModelType.by_value(model_type_value)
    else:
        errors.append('Model type not selected.')
        model_type = None

    if not is_blank(download_url):
        if not is_valid_url(download_url):
            errors.append('Download URL is incorrect')
        elif not DownloadManager.instance().check_url_can_be_handled(download_url):
            errors.append(f"Model can't be downloaded from URL: {download_url}")

    if not is_blank(backup_url):
        if not is_valid_url(backup_url):
            errors.append('Backup URL is incorrect')
        elif not DownloadManager.instance().check_url_can_be_handled(backup_url):
            errors.append(f"Model can't be downloaded from backup URL: {backup_url}")

    if not is_blank(url) and not is_valid_url(url):
        errors.append('Model URL is incorrect.')

    if not is_blank(download_path) and not is_directory_path_valid(download_path):
        errors.append('Download path is incorrect.')

    if model_type is not None and model_type == ModelType.OTHER and is_blank(download_path):
        errors.append('Download path for type "Other" must be defined.')

    if not is_blank(download_filename) and (not is_valid_filename(download_filename) or not is_filename_with_extension(download_filename)):
        errors.append('Download filename is incorrect.')

    if not is_blank(preview_url) and not is_valid_url(preview_url):
        errors.append('Preview URL is incorrect.')

    if not is_blank(download_subdir) and model_type is not None:
        if not is_blank(download_path):
            path = download_subdir
        else:
            path = env.get_model_path(model_type)
        dl_subdir = os.path.join(path, download_subdir)
        if not is_directory_path_valid(dl_subdir):
            errors.append(f'Download path with SUBDIR is incorrect: {dl_subdir}')

    if rename_filename and location != current_location:

        preview_current_location = find_preview_file(current_location)
        if preview_current_location:
            new_filename = os.path.splitext(location)[0]
            extension = os.path.splitext(preview_current_location)[1]
            preview_location = os.path.join(os.path.dirname(preview_current_location), new_filename + extension)
            os.rename(preview_current_location, preview_location)

        os.rename(current_location, location)

    if errors:
        return [
            gr.HTML.update(value=styled.alert_danger(errors), visible=True),
            back_token
        ]
    else:
        record_data = json.loads(record_data)
        record_id = '' if record_data.get('record_id') is None else record_data['record_id']

        if description_output.startswith('<[[token="'):
            end_index = description_output.index(']]>') + 3
            description = description_output[end_index:]
        else:
            description = description_output

        download_url = download_url.strip()
        backup_url = backup_url.strip()
        sha256_hash = ''

        old_record = None
        if record_id:
            old_record = env.storage.get_record_by_id(record_id)
            created_at = old_record.created_at
        else:
            created_at = time.time()

        if old_record is not None:
            if old_record.location == location:
                sha256_hash = old_record.sha256_hash
            elif os.path.isfile(location):
                sha256_hash = calculate_sha256(location)
        elif sha256_state is not None:
            sha256_hash = sha256_state
        elif os.path.isfile(location):
            sha256_hash = calculate_sha256(location)

        record = Record(
            id_=record_id,
            name=name.strip(),
            model_type=model_type,
            download_url=download_url,
            backup_url=backup_url,
            url=url.strip(),
            download_path=download_path.strip(),
            download_filename=download_filename.strip(),
            subdir=download_subdir.strip(),
            preview_url=preview_url.strip(),
            description=description.strip(),
            positive_prompts=positive_prompts.strip(),
            negative_prompts=negative_prompts.strip(),
            groups=groups,
            sha256_hash=sha256_hash,
            md5_hash='',
            location=location,
            created_at=created_at,
            weight=promptweight
        )

        logger.info('record to save: %s', record)

        if record_id is not None and record_id:
            env.storage.update_record(record)
        else:
            env.storage.add_record(record)

        return [
            gr.HTML.update(visible=False),
            generate_ui_token()
        ]


def _on_id_changed(record_data):
    record_data = json.loads(record_data)
    prefilled = None
    if record_data.get('record_id') is not None and record_data['record_id']:
        record = env.storage.get_record_by_id(record_data['record_id'])
    elif record_data.get('prefilled_json') is not None and record_data['prefilled_json']:
        try:
            prefilled_json = record_data['prefilled_json']
            prefilled = json.loads(r"" + prefilled_json)
            record = map_dict_to_record(prefilled.get('id_'), prefilled)
        except json.decoder.JSONDecodeError:
            prefilled_json = record_data['prefilled_json']
            prefilled_unescaped = html.unescape(prefilled_json)
            prefilled_slash_escaped = prefilled_unescaped.replace('\\', '\\\\')
            prefilled = json.loads(prefilled_slash_escaped)
            record = map_dict_to_record(prefilled.get('id_'), prefilled)
    else:
        record = None

    title = '## Add model' if record is None or prefilled is not None else '## Edit model'
    name = '' if record is None else record.name
    model_type = '' if record is None else record.model_type.value

    if record is None or not record.download_url:
        download_url = gr.Textbox.update(
            value='',
            label='Download URL:'
        )
    else:
        download_url = gr.Textbox.update(
            value=record.download_url,
            label="""Download URL: (If URL will be changed - SHA256, MD5 and file location will be erased.
                  Remove file manually or via remove-files only option)"""
        )
    backup_url = '' if record is None else record.backup_url
    preview_url = '' if record is None else record.preview_url
    url = '' if record is None else record.url
    download_path = '' if record is None else record.download_path
    download_filename = '' if record is None else record.download_filename
    download_subdir = '' if record is None else record.subdir
    description = '' if record is None else record.description
    positive_prompts = '' if record is None else record.positive_prompts
    negative_prompts = '' if record is None else record.negative_prompts
    record_groups = [] if record is None else record.groups
    sha256 = None if record is None or not bool(record.sha256_hash) else record.sha256_hash
    location = '' if record is None else (record.location if os.path.isfile(record.location) else '')

    available_groups = env.storage.get_available_groups()
    logger.info('Groups loaded: %s', available_groups)
    logger.info('Record groups: %s', record_groups)
    available_groups.sort()
    groups = gr.Dropdown.update(choices=available_groups, value=record_groups)

    if not description:
        description = f'<[[token="{generate_ui_token()}"]]>'
    else:
        description = f'<[[token="{generate_ui_token()}"]]>{description}'

    rename_filename_checkbox = ''

    weight = 1 if record is None else record.weight

    return [title, name, model_type, download_url, backup_url, preview_url, url, download_path, download_filename, download_subdir,
            description, positive_prompts, negative_prompts, groups, available_groups, gr.HTML.update(visible=False),
            sha256, location, _get_bind_location_dropdown_update(model_type, location), rename_filename_checkbox, location, weight]


def _get_bind_location_dropdown_update(model_type_value, current_location: str):
    if not model_type_value:
        return gr.Dropdown.update(
            visible=False,
            value='None',
            choices=['None']
        )

    model_type = ModelType.by_value(model_type_value)

    if model_type == ModelType.OTHER:
        return gr.Dropdown.update(
            visible=False,
            value='None',
            choices=['None']
        )

    lookup_dir = os.path.join(env.get_model_path(model_type), '')

    files_found = get_model_files_in_dir(lookup_dir)
    # files_exclude = env.storage.get_all_records_locations()
    # files_unbounded = [x for x in files_found if x not in files_exclude]

    choices = ['None']
    choices.extend(list(map(lambda l: l.replace(lookup_dir, ''), files_found)))

    chosen = 'None'
    if current_location:
        model_local_path = current_location.replace(env.get_model_path(model_type) + '/', '')
        model_local_path = model_local_path.replace(lookup_dir, '')
        if model_local_path in choices:
            chosen = model_local_path

    return gr.Dropdown.update(
        visible=True,
        choices=choices,
        value=chosen,
        label=f'Bind with local file (in {lookup_dir})'
    )


def _on_model_type_changed(model_type_value, current_location):
    return _get_bind_location_dropdown_update(model_type_value, current_location)


def _on_add_groups_button_click(new_groups_str: str, selected_groups, available_groups):
    logger.info('new_groups_str: %s', new_groups_str)
    logger.info('selected_groups: %s', selected_groups)
    logger.info('available_groups: %s', available_groups)

    if available_groups is None:
        available_groups = []

    if selected_groups is None:
        selected_groups = []

    if new_groups_str:
        new_groups = new_groups_str.split(',')
        new_groups = [x.strip() for x in new_groups]
        available_groups.extend(new_groups)
        selected_groups.extend(new_groups)

    return [
        gr.Textbox.update(value=''),
        gr.Dropdown.update(choices=available_groups, value=selected_groups)
    ]


def _on_local_bind_change(model_file_name, model_type_value):
    if not model_type_value:
        return gr.Textbox.update(
            value='',
        )

    model_type = ModelType.by_value(model_type_value)
    if model_type == ModelType.OTHER:
        return gr.Textbox.update(
            value='',
        )
    model_dir_path = env.get_model_path(model_type)
    full_path = os.path.join(model_dir_path, model_file_name)
    if os.path.isfile(full_path):
        return gr.Textbox.update(full_path)
    else:
        return gr.Textbox.update('')

def _on_download_filename_change(rename_filename_checkbox, location, download_filename, current_location):
    if rename_filename_checkbox:
        return _on_rename_filename_checkbox_change(rename_filename_checkbox, location, download_filename, current_location)
    return current_location

def _on_rename_filename_checkbox_change(rename_filename_checkbox, location, download_filename, current_location):

    if rename_filename_checkbox:
        location_widget_label = "File location (renamed)"
        location_widget_value = os.path.join(os.path.dirname(location), download_filename)
    else:
        location_widget_label = "File location"
        location_widget_value = current_location

    location_widget = gr.Textbox.update(label=location_widget_label,
                                        value=location_widget_value)

    return location_widget

def edit_ui_block():
    edit_id_box = gr.Textbox(label='edit_id_box',
                             elem_classes='mo-alert-warning',
                             interactive=False,
                             visible=False)
    edit_back_box = gr.Textbox(label='edit_back_box',
                               elem_classes='mo-alert-warning',
                               interactive=False,
                               visible=False)

    sha256_preload_state = gr.State()

    title_widget = gr.Markdown()
    available_groups_state = gr.State()

    with gr.Row():
        with gr.Column():
            cancel_button = gr.Button('Cancel')
            name_widget = gr.Textbox(label='Name:',
                                     value='',
                                     max_lines=1,
                                     info='Model title to display (Required)',
                                     elem_id='model_organizer_edit_name')
            model_type_widget = gr.Dropdown(
                [model_type.value for model_type in ModelType],
                value='',
                label='Model type:',
                info='Model type (Required)')

            download_url_widget = gr.Textbox(label='Download URL:',
                                             value='',
                                             max_lines=1,
                                             info='Link to the model file (Optional)')
            with gr.Accordion(label='Backup URL (Optional)', open=False):
                backup_url_widget = gr.Textbox(label='Download from backup URL if download URL is unavailable',
                                                 value='',
                                                 max_lines=1)
            preview_url_widget = gr.Textbox(label='Preview image URL:',
                                            value='',
                                            max_lines=1,
                                            info='Link to the image for preview (Optional)'
                                            )
            url_widget = gr.Textbox(label='Model page URL:',
                                    value='',
                                    max_lines=1,
                                    info='Link to the model page (Optional)')

        with gr.Column():
            save_widget = gr.Button('Save', elem_classes='mo-alert-primary')

            error_widget = gr.HTML(visible=False)
            groups_widget = gr.Dropdown(label='Groups',
                                        multiselect=True,
                                        info='Select existing groups or add new.',
                                        interactive=True,
                                        elem_id='mo-groups-widget'
                                        )
            with gr.Accordion(label='Add groups', open=False):
                with gr.Row():
                    add_groups_box = gr.Textbox(label='Add new group',
                                                max_lines=1,
                                                info='Type comma-separated group names',
                                                elem_id='mo-add-groups-box')
                    add_groups_button = gr.Button('Add Group')

            location_widget = gr.Textbox(label="File location",
                                         info="Local file location path. Not editable.",
                                         interactive=False)

            location_bind_widget = gr.Dropdown(label='Bind with local file',
                                               info='Choose a local file to associate this record with.',
                                               interactive=True,
                                               elem_id='model_organizer_add_bind')

            with gr.Accordion(label='Download options', open=False):
                download_path_widget = gr.Textbox(label='Download Path:',
                                                  value='',
                                                  max_lines=1,
                                                  info='Path to the download dir, default if empty. '
                                                       '(Required for "Other\" model type)', )
                download_filename_widget = gr.Textbox(label='Download File Name:',
                                                      value='',
                                                      max_lines=1,
                                                      info='Downloaded file name with extension. Default if empty ('
                                                           'Optional)')
                rename_filename_checkbox_widget = gr.Checkbox(label='Rename local filename if download filename is presented.',
                                                              value=False)
                current_location_widget = gr.Textbox(label="Current File location",
                                                     info="Local file location path. Not editable.",
                                                     interactive=False,
                                                     visible=False)
                download_subdir_widget = gr.Textbox(label='Subdir',
                                                    value='',
                                                    max_lines=1,
                                                    info='Download file into sub directory (Optional)')

            with gr.Accordion(label='Prompts', open=False):
                positive_prompts_widget = gr.Textbox(label='Positive prompts:',
                                                     value='',
                                                     max_lines=20,
                                                     info='Model positive prompts (Optional)')
                prompt_weight_slider = gr.Slider(label='Preferred weight',
                                                     info="Default value",
                                                     minimum=0.0,
                                                     maximum=2.0,
                                                     step=0.01,
                                                     elem_id='mo-edit-prompt-weight')
                negative_prompts_widget = gr.Textbox(label='Negative prompts:',
                                                     value='',
                                                     max_lines=20,
                                                     info='Model negative prompts (Optional)')

    description_html = '<div><p style="margin-left: 0.2rem;">Description:</p>' \
                       '<textarea id="mo-description-editor"></textarea></div>'
    gr.HTML(label='Description:', value=description_html)

    description_input_widget = gr.Textbox(label='description_input_widget',
                                          elem_classes='mo-alert-warning',
                                          interactive=False,
                                          visible=False)
    description_output_widget = gr.Textbox(label="description_output_widget",
                                           elem_classes='mo-alert-warning',
                                           elem_id='mo-description-output-widget',
                                           interactive=False,
                                           visible=False)

    description_input_widget.change(fn=None, inputs=description_input_widget,
                                    _js='handleDescriptionEditorContentChange')

    description_output_widget.change(_on_description_output_changed,
                                     inputs=[edit_id_box, name_widget, model_type_widget,
                                             download_url_widget, backup_url_widget, url_widget,
                                             download_path_widget, download_filename_widget, rename_filename_checkbox_widget, download_subdir_widget,
                                             preview_url_widget, description_output_widget, positive_prompts_widget,
                                             negative_prompts_widget, groups_widget, edit_back_box,
                                             sha256_preload_state, location_widget, current_location_widget, prompt_weight_slider],
                                     outputs=[error_widget, edit_back_box])

    edit_id_box.change(_on_id_changed,
                       inputs=edit_id_box,
                       outputs=[title_widget, name_widget, model_type_widget, download_url_widget, backup_url_widget,
                                preview_url_widget, url_widget, download_path_widget, download_filename_widget,
                                download_subdir_widget, description_input_widget, positive_prompts_widget,
                                negative_prompts_widget, groups_widget, available_groups_state, error_widget,
                                sha256_preload_state, location_widget, location_bind_widget, rename_filename_checkbox_widget, current_location_widget, prompt_weight_slider]
                       )

    download_filename_widget.change(_on_download_filename_change,
                                    inputs=[rename_filename_checkbox_widget, location_widget, download_filename_widget, current_location_widget],
                                    outputs=location_widget)

    rename_filename_checkbox_widget.change(_on_rename_filename_checkbox_change,
                                           inputs=[rename_filename_checkbox_widget, location_widget, download_filename_widget, current_location_widget],
                                           outputs=[location_widget])

    model_type_widget.change(_on_model_type_changed,
                             inputs=[model_type_widget, location_widget],
                             outputs=[location_bind_widget])

    location_bind_widget.change(_on_local_bind_change,
                                inputs=[location_bind_widget, model_type_widget],
                                outputs=location_widget)

    save_widget.click(fn=None, _js='handleRecordSave')

    add_groups_button.click(_on_add_groups_button_click,
                            inputs=[add_groups_box, groups_widget, available_groups_state],
                            outputs=[add_groups_box, groups_widget])

    cancel_button.click(fn=None, _js='navigateBack')
    edit_back_box.change(fn=None, _js='navigateBack')

    return edit_id_box
