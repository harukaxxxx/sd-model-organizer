import json

import gradio as gr

import scripts.mo.ui_styled_html as styled
from scripts.mo.data.record_utils import load_records_and_filter
from scripts.mo.environment import env, LAYOUT_CARDS
from scripts.mo.models import ModelType, ModelSort


def _prepare_data(state_json: str):
    state = json.loads(state_json)

    records = load_records_and_filter(state, True)

    if env.layout() == LAYOUT_CARDS:
        html = styled.records_cards(records)
    else:
        html = styled.records_table(records)

    return [
        html,
        gr.Button.update(visible=len(records) > 0),
        gr.Dropdown.update(value=state['groups'], choices=_get_available_groups())
    ]


def _get_available_groups():
    return env.storage.get_available_groups()


def _on_sort_order_changed(sort_order, state_json):
    state = json.loads(state_json)
    state['sort_order'] = sort_order
    settings = env.read_settings()
    settings['sort_order'] = sort_order
    env.save_settings(settings)
    return json.dumps(state)


def _on_downloaded_first_changed(sort_downloaded_first, state_json):
    state = json.loads(state_json)
    state['sort_downloaded_first'] = sort_downloaded_first
    settings = env.read_settings()
    settings['sort_downloaded_first'] = sort_downloaded_first
    env.save_settings(settings)
    return json.dumps(state)


def _on_search_query_changed(query, state_json):
    state = json.loads(state_json)
    state['query'] = query
    return json.dumps(state)


def _on_model_type_box_changed(selected, state_json):
    state = json.loads(state_json)
    state['model_types'] = selected
    return json.dumps(state)


def _on_group_box_changed(selected, state_json):
    state = json.loads(state_json)
    state['groups'] = selected
    return json.dumps(state)


def _on_show_downloaded_changed(show_downloaded, state_json):
    state = json.loads(state_json)
    state['show_downloaded'] = show_downloaded
    return json.dumps(state)


def _on_show_not_downloaded_changed(show_not_downloaded, state_json):
    state = json.loads(state_json)
    state['show_not_downloaded'] = show_not_downloaded
    return json.dumps(state)


def _on_show_local_files_changed(show_not_downloaded, state_json):
    state = json.loads(state_json)
    state['show_local_files'] = show_not_downloaded
    return json.dumps(state)


def home_ui_block():
    settings = env.read_settings()

    if settings.get('sort_order') is not None:
        sort_order = settings['sort_order']
    else:
        sort_order = ModelSort.TIME_ADDED_ASC.value

    if settings.get('sort_downloaded_first') is not None:
        sort_downloaded_first = True if settings['sort_downloaded_first'].lower() == "true" else False
    else:
        sort_downloaded_first = False

    initial_state = {
        'query': '',
        'model_types': [],
        'groups': [],
        'show_downloaded': True,
        'show_not_downloaded': True,
        'show_local_files': True,
        'sort_order': sort_order,
        'sort_downloaded_first': sort_downloaded_first
    }
    initial_state_json = json.dumps(initial_state)

    with gr.Blocks():
        refresh_box = gr.Textbox(label='refresh_box',
                                 elem_classes='mo-alert-warning',
                                 visible=False,
                                 interactive=False)

        state_box = gr.Textbox(value='',
                               label='state_box',
                               elem_classes='mo-alert-warning',
                               elem_id='mo-home-state-box',
                               visible=False,
                               interactive=False)

        gr.Textbox(value=initial_state_json,
                   label='initial_state_box',
                   elem_classes='mo-alert-warning',
                   elem_id='mo-initial-state-box',
                   visible=False,
                   interactive=False)

        with gr.Row():
            gr.Markdown('## Records list')
            if not env.is_debug_mode_enabled():
                gr.Markdown('')
            debug_button = gr.Button('🛠️ Debug', visible=env.is_debug_mode_enabled())
            reload_button = gr.Button('🔄 Reload')
            download_all_button = gr.Button('📥 Download All', visible=False)
            import_export_button = gr.Button('↩️ Import/Export')
            add_button = gr.Button('🆕 Add')

        with gr.Accordion(label='Display options', open=False, elem_id='model_organizer_accordion'):
            with gr.Group():
                sort_box = gr.Dropdown([model_sort.value for model_sort in ModelSort],
                                       value=sort_order,
                                       label='Sort By',
                                       multiselect=False,
                                       interactive=True)

                downloaded_first_checkbox = gr.Checkbox(value=sort_downloaded_first, label='Downloaded first')

            with gr.Group():
                search_box = gr.Textbox(label='Search by name',
                                        value=initial_state['query'], elem_id='model_organizer_searchbox')
                model_types_dropdown = gr.Dropdown([model_type.value for model_type in ModelType],
                                                   value=initial_state['model_types'],
                                                   label='Model types',
                                                   multiselect=True)
                groups_dropdown = gr.Dropdown(_get_available_groups(),
                                              multiselect=True,
                                              label='Groups',
                                              value=initial_state['groups'])
                show_downloaded_checkbox = gr.Checkbox(label='Show downloaded',
                                                       value=initial_state['show_downloaded'])
                show_not_downloaded_checkbox = gr.Checkbox(label='Show not downloaded',
                                                           value=initial_state['show_not_downloaded'])
                show_local_files_checkbox = gr.Checkbox(label='Show local files',
                                                        value=initial_state['show_local_files'])

        html_content_widget = gr.HTML()

        reload_button.click(_prepare_data, inputs=state_box,
                            outputs=[html_content_widget, download_all_button, groups_dropdown])
        refresh_box.change(_prepare_data, inputs=state_box,
                           outputs=[html_content_widget, download_all_button, groups_dropdown])
        state_box.change(_prepare_data, inputs=state_box,
                         outputs=[html_content_widget, download_all_button, groups_dropdown])

        debug_button.click(fn=None, _js='navigateDebug')
        download_all_button.click(fn=None, inputs=state_box, _js='navigateDownloadRecordList')
        import_export_button.click(fn=None, inputs=state_box, _js='navigateImportExport')
        add_button.click(fn=None, _js='navigateAdd')

        sort_box.change(_on_sort_order_changed,
                        inputs=[sort_box, state_box],
                        outputs=state_box)

        downloaded_first_checkbox.change(_on_downloaded_first_changed,
                                         inputs=[downloaded_first_checkbox, state_box],
                                         outputs=state_box)

        search_box.change(_on_search_query_changed, inputs=[search_box, state_box], outputs=state_box)
        model_types_dropdown.change(_on_model_type_box_changed, inputs=[model_types_dropdown, state_box],
                                    outputs=state_box)
        groups_dropdown.change(_on_group_box_changed, inputs=[groups_dropdown, state_box], outputs=state_box)

        show_downloaded_checkbox.change(_on_show_downloaded_changed,
                                        inputs=[show_downloaded_checkbox, state_box],
                                        outputs=state_box)
        show_not_downloaded_checkbox.change(_on_show_not_downloaded_changed,
                                            inputs=[show_not_downloaded_checkbox, state_box],
                                            outputs=state_box)
        show_local_files_checkbox.change(_on_show_local_files_changed,
                                         inputs=[show_local_files_checkbox, state_box],
                                         outputs=state_box)

    return refresh_box
