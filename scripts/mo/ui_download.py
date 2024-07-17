import json
import time

import gradio as gr

import scripts.mo.ui_format as ui_format
import scripts.mo.ui_navigation as nav
import scripts.mo.ui_styled_html as styled
from scripts.mo.dl.download_manager import *
from scripts.mo.environment import env, logger
from scripts.mo.data.record_utils import load_records_and_filter

_STATE_PENDING = 'Pending'
_STATE_IN_PROGRESS = 'In Progress'
_STATE_COMPLETED = 'Completed'
_STATE_EXISTS = 'Exists'
_STATE_ERROR = 'Error'


def _build_widget_update(progress_update=None, status_message=None, is_start_button_visible=None,
                         is_cancel_button_visible=None,
                         is_back_button_visible=None):
    upd = [
        gr.HTML.update() if status_message is None else gr.HTML.update(value=status_message, visible=True),
        gr.Button.update() if is_start_button_visible is None else gr.Button.update(visible=is_start_button_visible),
        gr.Button.update() if is_cancel_button_visible is None else gr.Button.update(visible=is_cancel_button_visible),
        gr.Button.update() if is_back_button_visible is None else gr.Button.update(visible=is_back_button_visible),
        gr.Textbox.update() if progress_update is None else gr.Textbox.update(value=progress_update)
    ]
    return upd


def _generate_info_center(bytes_ready, bytes_total):
    if isinstance(bytes_ready, int) and isinstance(bytes_total, int) and bytes_total > 0:
        return f"{ui_format.format_bytes(bytes_ready)} / {ui_format.format_bytes(bytes_total)}"
    else:
        if isinstance(bytes_ready, int):
            return ui_format.format_bytes(bytes_ready)
    return ''


def _generate_progress(bytes_ready, bytes_total):
    if isinstance(bytes_ready, int) and isinstance(bytes_total, int) and bytes_total > 0:
        return ui_format.format_percentage(bytes_ready, bytes_total)
    else:
        return 0


def _generate_info_right(speed_rate, elapsed):
    speed = ui_format.format_download_speed(speed_rate) if isinstance(speed_rate, float) and speed_rate > 0 else ''
    elapsed = '' if not isinstance(elapsed, float) or elapsed == 0 else ui_format.format_time(elapsed)
    right_info = ''
    if speed:
        right_info += speed
    if speed and elapsed:
        right_info += ' | '
    if elapsed:
        right_info += elapsed

    return right_info


def _generate_js_record_update(record_id, update):
    result = {'id': record_id}

    status = update.get('status')
    if status is not None:
        result['status'] = status

    if status is not None:
        if status == RECORD_STATUS_EXISTS:
            result['result_title'] = 'File already exists.'
            if update.get('destination') is not None:
                result['result_text'] = update['destination']

        elif status == RECORD_STATUS_COMPLETED:
            result['result_title'] = 'Download completed.'
            result_text = ''

            if update.get('destination') is not None:
                result_text += update['destination']

            if update.get('preview_destination'):
                result_text += '<br>' if len(result_text) > 0 else ''
                result_text += update['preview_destination']

            if len(result_text) > 0:
                result['result_text'] = result_text

        elif status == RECORD_STATUS_ERROR:
            result['result_title'] = 'Download failed'
            if update.get('exception') is not None:
                result['result_text'] = ui_format.format_exception(update['exception'])

        elif status == RECORD_STATUS_CANCELLED:
            result['result_title'] = 'Download cancelled'

    if update.get('filename') is not None:
        result['progress_info_left'] = update['filename']

    if update.get('dl') is not None:
        dl = update['dl']
        result['progress_info_center'] = _generate_info_center(dl['bytes_ready'], dl['bytes_total'])
        result['progress_info_right'] = _generate_info_right(dl['speed_rate'], dl['elapsed'])
        result['progress'] = _generate_progress(dl['bytes_ready'], dl['bytes_total'])

    if update.get('preview_dl') is not None:
        dl = update['preview_dl']
        result['progress_preview_info_center'] = _generate_info_center(dl['bytes_ready'], dl['bytes_total'])
        result['progress_preview_info_right'] = _generate_info_right(dl['speed_rate'], dl['elapsed'])
        result['progress_preview'] = _generate_progress(dl['bytes_ready'], dl['bytes_total'])

    return result


def _generate_general_update(update):
    status_message = None

    is_start_button_visible = None
    is_cancel_button_visible = None
    is_back_button_visible = None

    if update.get('general_status') is not None:
        if update['general_status'] == GENERAL_STATUS_IN_PROGRESS:
            status_message = styled.alert_primary('Download in progress.')
            is_start_button_visible = False
            is_cancel_button_visible = True
            is_back_button_visible = False

        elif update['general_status'] == GENERAL_STATUS_COMPLETED:
            status_message = styled.alert_success('Download completed.')
            is_start_button_visible = False
            is_cancel_button_visible = False
            is_back_button_visible = True

        elif update['general_status'] == GENERAL_STATUS_CANCELLED:
            status_message = styled.alert_warning('Download cancelled')
            is_start_button_visible = True
            is_cancel_button_visible = False
            is_back_button_visible = True

        elif update['general_status'] == GENERAL_STATUS_ERROR:
            stat = ['Download failed.']
            if update.get('exception') is not None:
                stat.append(ui_format.format_exception(update['exception']))
            status_message = styled.alert_danger(stat)

            is_start_button_visible = True
            is_cancel_button_visible = False
            is_back_button_visible = True

    js_result = {}
    if update.get('records') is not None:
        upd_list = []
        for record_id, upd in update['records'].items():
            upd_list.append(_generate_js_record_update(record_id, upd))
        js_result['records'] = upd_list

    return _build_widget_update(
        progress_update=json.dumps(js_result) if bool(js_result) else None,
        status_message=status_message,
        is_start_button_visible=is_start_button_visible,
        is_cancel_button_visible=is_cancel_button_visible,
        is_back_button_visible=is_back_button_visible,
    )


def _on_start_click(records):
    yield _build_widget_update(
        status_message=styled.alert_primary('Download in progress.'),
        is_start_button_visible=False,
        is_cancel_button_visible=True,
        is_back_button_visible=False,
    )

    DownloadManager.instance().start_download(records)

    counter = 0
    while DownloadManager.instance().is_running():
        if counter % 20 == 0:
            download_state = DownloadManager.instance().get_state()
        else:
            download_state = DownloadManager.instance().get_latest_state()
        yield _generate_general_update(download_state)
        time.sleep(0.2)

    general_state = DownloadManager.instance().get_state()

    yield _generate_general_update(general_state)
    logger.debug('Completed.')


def _on_id_change(data):
    logger.info(f'download id data changed = {data}')

    if not data:
        return [
            gr.HTML.update(),
            [],
            gr.Button.update(visible=False),  # start_button
            gr.Button.update(visible=False),  # cancel_button
            gr.Button.update(visible=True),  # back_button
            gr.HTML.update(value=styled.alert_warning('Nothing passed to download.'),
                           visible=True)  # status_message_widget
        ]

    records = []
    record_id = nav.get_download_record_id(data)
    group = nav.get_download_group(data)
    filter_state = nav.get_download_filter_state(data)

    if record_id is not None:
        records.append(env.storage.get_record_by_id(record_id))

    if group is not None:
        records.extend(env.storage.get_records_by_group(group))

    if filter_state is not None:
        state = json.loads(filter_state)
        records.extend(load_records_and_filter(state, False))

    return [
        gr.HTML.update(value=styled.download_cards(records, nav.generate_ui_token())),
        records,
        gr.Button.update(visible=True),  # start_button
        gr.Button.update(visible=False),  # cancel_button
        gr.Button.update(visible=True),  # back_button
        gr.HTML.update(visible=False)  # status_message_widget
    ]


def _on_cancel_click():
    DownloadManager.instance().stop_download()


def download_ui_block():
    with gr.Blocks():
        download_state = gr.State(value=[])
        download_id_box = gr.Textbox(label='download_id_box',
                                     elem_classes='mo-alert-warning',
                                     visible=False,
                                     interactive=False)
        download_progress_box = gr.Textbox(label='download_progress_box',
                                           elem_classes='mo-alert-warning',
                                           visible=False,
                                           interactive=False)
        gr.Markdown('## Downloads')
        status_message_widget = gr.HTML(visible=False)
        with gr.Row():
            gr.Markdown()
            back_button = gr.Button('⬅️ Back', visible=True)
            start_button = gr.Button('📥 Start Download', visible=True)
            cancel_button = gr.Button('❎ Cancel Download', visible=False)
            gr.Markdown()
        gr.HTML('</hr>')
        html_widget = gr.HTML()

    download_id_box.change(_on_id_change, inputs=download_id_box,
                           outputs=[html_widget, download_state, start_button, cancel_button, back_button,
                                    status_message_widget])
    download_progress_box.change(fn=None, inputs=download_progress_box, _js='handleProgressUpdates')

    start_button.click(_on_start_click, inputs=download_state,
                       outputs=[status_message_widget, start_button, cancel_button, back_button, download_progress_box])

    cancel_button.click(_on_cancel_click, queue=False)
    back_button.click(fn=None, _js='navigateBack')

    return download_id_box
