// add tinymce
const script = document.createElement('script');
script.src = 'file=extensions/sd-model-organizer/javascript/tinymce/tinymce.min.js';
document.head.appendChild(script);

let isHomeInitialStateInvoked = false

/**
 * Finds an element in document.
 * @param elementId - element id.
 * @returns {*}
 */
function findElem(elementId) {
    return document.getElementById(elementId)
    // return gradioApp().getElementById(elementId)
}

/**
 * Prints log into console. Must be disabled before merging into main branch.
 * @param text
 */
function logMo(text) {
    // console.log(text)
}

/**
 * Creates tinymce instance if it doesn't exist, setups theme and NOT editable content.
 * @param content - html content to display.
 * @param theme - theme to setup, 'dark' for dark theme and others for light one.
 */
function setupDescriptionPreview(content, theme) {
    if (tinymce.get('mo-description-preview') == null) {
        tinymce.init({
            selector: '#mo-description-preview',
            toolbar: false,
            menubar: false,
            statusbar: false,
            promotion: false,
            plugins: 'autoresize',
            skin: theme === 'dark' ? 'oxide-dark' : 'oxide',
            content_css: theme === 'dark' ? 'dark' : 'default',
            init_instance_callback: function (inst) {
                inst.mode.set("readonly")
                inst.setContent(content)
            }
        });
    }

    const inst = tinymce.get('mo-description-preview')
    if (inst.initialized) {
        inst.setContent(content)
    }
}

/**
 * Function called from gradio to set description preview NOT editable content.
 * @param content - content to display.
 * @returns {*[]} Gradio wants an array returned.
 */
function handleDescriptionPreviewContentChange(content) {
    logMo('handleDescriptionPreviewContentChange')

    getTheme()
        .then(theme => {
            setupDescriptionPreview(content, theme)
        })

    return []
}

/**
 * Creates tinymce instance if it doesn't exist, setups theme and editable content.
 * @param content - html content to display and edit.
 * @param theme - theme to setup, 'dark' for dark theme and others for light one.
 */
function setupDescriptionEdit(content, theme) {
    let contentData = content.replace(/<\[\[token=".*?"]]>/, '');

    if (tinymce.get('mo-description-editor') == null) {
        tinymce.init({
            selector: '#mo-description-editor',
            promotion: false,
            plugins: 'anchor autolink charmap codesample emoticons image link lists media searchreplace table visualblocks',
            toolbar: 'undo redo | blocks fontfamily fontsize | bold italic underline strikethrough | link image media table mergetags | addcomment showcomments | spellcheckdialog a11ycheck typography | align lineheight | checklist numlist bullist indent outdent | emoticons charmap | removeformat',
            skin: theme === 'dark' ? 'oxide-dark' : 'oxide',
            content_css: theme === 'dark' ? 'dark' : 'default',
            init_instance_callback: function (inst) {
                inst.setContent(contentData)
            }
        });
    }

    const inst = tinymce.get('mo-description-editor')
    if (inst.initialized) {
        inst.setContent(contentData)
    }
}

/**
 * Function called from gradio to set description editable content.
 * @param content - content to edit.
 * @returns {*[]} Gradio wants an array returned.
 */
function handleDescriptionEditorContentChange(content) {
    logMo('handleDescriptionEditorContentChange')

    getTheme()
        .then(theme => {
            setupDescriptionEdit(content, theme)
        })

    return []
}

function handleRecordSave() {
    logMo('Handling record save')

    // This random token required to trigger change event in gradio in the textbox widget :/
    const token = '<[[token="' + generateUUID() + '"]]>'

    let output;
    if (tinymce.get('mo-description-editor') == null) {
        output = token
    } else {
        output = token + tinymce.get('mo-description-editor').getContent()
    }

    const textArea = findElem('mo-description-output-widget').querySelector('textarea')
    const event = new Event('input', { 'bubbles': true, "composed": true });
    textArea.value = output
    findElem('mo-description-output-widget').querySelector('textarea').dispatchEvent(event);
    logMo('Description content dispatched: ' + output)
    return []
}

function updateDownloadBlockVisibility(id, tag, isVisible, visibleUnit) {
    const block = findElem(tag + '-' + id)
    const previewBlock = findElem(tag + '-preview-' + id)

    if (block) {
        block.style.display = isVisible ? visibleUnit : 'none'
        logMo(block.id + " display =" + block.style.display)
    }

    if (previewBlock) {
        previewBlock.style.display = isVisible ? visibleUnit : 'none'
        logMo(previewBlock.id + " display =" + previewBlock.style.display)
    }
}

function updateDownloadCardState(id, state) {
    let cardClass = ''
    let isUrlVisible = false
    let isDownloadProgressVisible = false
    let isResultBoxVisible = false

    if (state === 'Pending') {
        cardClass = 'mo-alert-secondary'
        isUrlVisible = true
    } else if (state === 'In Progress') {
        cardClass = 'mo-alert-primary'
        isUrlVisible = true
        isDownloadProgressVisible = true
    } else if (state === 'Completed') {
        cardClass = 'mo-alert-success'
        isResultBoxVisible = true
    } else if (state === 'Exists') {
        cardClass = 'mo-alert-info'
        isResultBoxVisible = true
    } else if (state === 'Error') {
        cardClass = 'mo-alert-danger'
        isResultBoxVisible = true
    } else if (state === 'Cancelled') {
        cardClass = 'mo-alert-warning'
    } else {
        return
    }
    logMo(cardClass)
    const className = 'mo-downloads-card ' + cardClass
    logMo(className)
    const cardElement = findElem('download-card-' + id)
    cardElement.className = className
    findElem('status-' + id).textContent = state

    updateDownloadBlockVisibility(id, 'url', isUrlVisible, 'block')
    updateDownloadBlockVisibility(id, 'info-bar', isDownloadProgressVisible, 'flex')
    updateDownloadBlockVisibility(id, 'progress', isDownloadProgressVisible, 'flex')
    updateDownloadBlockVisibility(id, 'result-box', isResultBoxVisible, 'block')
}

function updateResultText(id, title, text) {
    const elem = findElem('result-box-' + id)
    if (elem) {
        let resultContent = '<p>' + title + ':</p>'
        if (Array.isArray(text)) {
            text.forEach(function (txt) {
                resultContent += '<p style="margin-left: 1rem; padding: 0 !important; line-height: 1.4 !important;">'
                resultContent += txt
                resultContent += '</p>'
            });
        } else {
            resultContent += '<p style="margin-left: 1rem; padding: 0 !important; line-height: 1.4 !important;">'
            resultContent += text
            resultContent += '</p>'
        }
        elem.innerHTML = resultContent
    }
}

function updateText(id, tag, isPreview, value) {
    const p = isPreview ? '-preview-' : '-'
    const elem = findElem(tag + p + id)
    if (elem) {
        elem.textContent = value
    }
}

function updateProgressBar(id, tag, isPreview, value) {
    const p = isPreview ? '-preview-' : '-'
    const elem = findElem(tag + p + id)
    if (elem) {
        const val = value + '%'
        elem.style.width = val
        elem.textContent = val
    }
}

function handleProgressUpdates(value) {
    const data = JSON.parse(value);

    if (data.hasOwnProperty('records')) {
        data.records.forEach(function (item, index) {
            handleRecordUpdates(item)
        });
    }

    return []
}

function handleRecordUpdates(data) {
    const id = data.id;

    if (data.hasOwnProperty('status')) {
        updateDownloadCardState(id, data.status)
    }

    if (data.hasOwnProperty('result_text')) {
        let resultTitle = data.hasOwnProperty('result_title') ? data.result_title : 'Result'
        updateResultText(id, resultTitle, data.result_text)
    }

    if (data.hasOwnProperty('progress_info_left')) {
        updateText(id, 'progress-info-left', false, data.progress_info_left)
    }

    if (data.hasOwnProperty('progress_info_center')) {
        updateText(id, 'progress-info-center', false, data.progress_info_center)
    }

    if (data.hasOwnProperty('progress_info_right')) {
        updateText(id, 'progress-info-right', false, data.progress_info_right)
    }

    if (data.hasOwnProperty('progress_preview_info_left')) {
        updateText(id, 'progress-info-left', true, data.progress_preview_info_left)
    }

    if (data.hasOwnProperty('progress_preview_info_center')) {
        updateText(id, 'progress-info-center', true, data.progress_preview_info_center)
    }

    if (data.hasOwnProperty('progress_preview_info_right')) {
        updateText(id, 'progress-info-right', true, data.progress_preview_info_right)
    }

    if (data.hasOwnProperty('progress')) {
        updateProgressBar(id, 'progress-bar', false, data.progress)
    }

    if (data.hasOwnProperty('progress_preview')) {
        updateProgressBar(id, 'progress-bar', true, data.progress_preview)
    }
}

function generateUUID() {
    let d = new Date().getTime();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = (d + Math.random() * 16) % 16 | 0;
        d = Math.floor(d / 16);
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

function populateBackstack() {
    const textArea = findElem('mo_json_nav_box').querySelector('textarea')
    const currentNavigationJson = textArea.value
    const backstack = []
    if (Boolean(currentNavigationJson)) {

        const currentNavigation = JSON.parse(currentNavigationJson);
        logMo('Current Navigation: ' + currentNavigation)

        if (currentNavigation.hasOwnProperty('backstack')) {
            currentNavigation.backstack.forEach(function (item, index) {
                backstack.push(item);
            });
            delete currentNavigation.backstack;
        }

        if (currentNavigation.hasOwnProperty('token')) {
            delete currentNavigation.token;
        }
        logMo('previous backstack: ' + backstack)

        backstack.unshift(currentNavigation);
        logMo('new backstack: ' + backstack)
    }
    return backstack
}

function navigateHome() {
    logMo('Navigate home screen')
    const navObj = {};
    deliverNavObject(navObj)
    return []
}

function navigateBack() {
    const textArea = findElem('mo_json_nav_box').querySelector('textarea')
    const currentNavigationJson = textArea.value
    let backNav = {}
    if (Boolean(currentNavigationJson)) {
        const currentNavigation = JSON.parse(currentNavigationJson);
        logMo('Current Navigation: ' + currentNavigation)

        if (currentNavigation.hasOwnProperty('backstack') && currentNavigation.backstack.length !== 0) {
            backNav = currentNavigation.backstack.shift()

            if (currentNavigation.backstack.length !== 0) {
                backNav.backstack = currentNavigation.backstack
            }
        }
    }
    deliverNavObject(backNav)
    return []
}

function navigateDetails(id, event) {
    if (event !== undefined) {
        event.stopPropagation();
        event.preventDefault();
    }
    logMo('Navigate details screen for id: ' + id)
    const navObj = {
        screen: "details",
        record_id: id,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateAdd() {
    logMo('Navigate add screen')
    const navObj = {
        screen: "edit",
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateImportExport(filter_state) {
    logMo('Navigate import_export screen')
    const navObj = {
        screen: "import_export",
        token: generateUUID(),
        backstack: populateBackstack(),
        filter_state: filter_state
    };
    deliverNavObject(navObj)
    return []
}

function navigateDebug(event) {
    logMo('Navigate debug screen')
    const navObj = {
        screen: "debug",
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateEdit(id, event) {
    if (event !== undefined) {
        event.stopPropagation();
        event.preventDefault();
    }
    logMo('Navigate edit screen for id: ' + id)
    const navObj = {
        screen: "edit",
        record_id: id,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateEditPrefilled(json_data, event) {
    if (event !== undefined) {
        event.stopPropagation();
        event.preventDefault();
    }
    logMo('Navigate edit screen for prefilled json: ' + json_data)
    const navObj = {
        screen: "edit",
        prefilled_json: json_data,
        token: generateUUID(),
        backstack: populateBackstack()
    };


    setTimeout((event) => {
            //Get config options
            var json_elem = gradioApp().getElementById('settings_json');
            if (json_elem == null) return;

            var textarea = json_elem.querySelector('textarea');
            var jsdata = textarea.value;
            opts = JSON.parse(jsdata);




            // record_data = gradioApp().querySelector('#mo_record_info_nav_box textarea');

            // if (record_data == null) return;
            // var terminate = false;
            // var jsdata = record_data.value;
            // var jsdata = jsdata.replace(/'/g, '"').replace(/"checkpoint": True/mg, '"checkpoint": true').replace(/"checkpoint": False/mg, '"checkpoint": false');
            // recordInfo = JSON.parse(jsdata);

            // var weight = gradioApp().querySelector('#mo-edit-prompt-weight');
            // weight.value = recordInfo["weight"];
            // weight.dispatchEvent(changeEvent);

            if (opts['mo_autobind_file']) {
                var bind = gradioApp().querySelector('#model_organizer_add_bind input');
                var modelName = gradioApp().querySelector('#model_organizer_edit_name input');
                bind.value = modelName.value;
                bind.dispatchEvent(changeEvent);
                terminate = true;
            }
    }, 300);
    deliverNavObject(navObj)


    return []
}

function navigateDownloadRecord(id, event) {
    if (event !== undefined) {
        event.stopPropagation();
        event.preventDefault();
    }
    logMo('Navigate download screen for id: ' + id)
    const navObj = {
        screen: "download",
        record_id: id,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateDownloadRecordList(filter_state) {
    logMo('Navigate download screen for records with filter state: ' + filter_state)
    const navObj = {
        screen: "download",
        filter_state: filter_state,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateDownloadGroup(groupName) {
    logMo('Navigate download screen for group: ' + groupName)
    const navObj = {
        screen: "download",
        group: groupName,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function navigateRemove(id, event) {
    if (event !== undefined) {
        event.stopPropagation();
        event.preventDefault();
    }
    logMo('Navigate removal screen for id: ' + id)
    const navObj = {
        screen: "remove",
        record_id: id,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)
    return []
}

function deliverNavObject(navObj) {
    const navJson = JSON.stringify(navObj);
    const textArea = findElem('mo_json_nav_box').querySelector('textarea')
    const event = new Event('input', { 'bubbles': true, "composed": true });
    textArea.value = navJson
    findElem('mo_json_nav_box').querySelector('textarea').dispatchEvent(event);
    logMo('JSON Nav dispatched: ' + navJson)
}

function invokeHomeInitialStateLoad() {
    logMo('invokeHomeInitialStateLoad')
    if (!isHomeInitialStateInvoked) {
        const initialStateTextArea = findElem('mo-initial-state-box').querySelector('textarea')
        const stateTextArea = findElem('mo-home-state-box').querySelector('textarea')
        stateTextArea.value = initialStateTextArea.value
        const event = new Event('input', { 'bubbles': true, "composed": true });
        findElem('mo-home-state-box').querySelector('textarea').dispatchEvent(event);
        isHomeInitialStateInvoked = true
        logMo('initial home state invoked')
    }
    return []
}

function getTheme() {
    return new Promise((resolve, _) => {
        const parsedUrl = new URL(window.location.href)
        const theme = parsedUrl.searchParams.get('__theme')
        if (theme != null) {
            logMo('theme resolved: ' + theme)
            resolve(theme)
        } else {
            fetch(origin + '/mo/display-options')
                .then(response => response.json())
                .then(data => {
                    logMo('display options received:')
                    logMo(data)
                    resolve(data.theme)
                })
                .catch(_ => {
                    resolve('light')
                });
        }
    });
}

function getCardsSize() {
    return new Promise((resolve) => {
        fetch(origin + '/mo/display-options')
            .then(response => response.json())
            .then(data => {
                resolve([data.card_width, data.card_height])
            })
            .catch(_ => {
                resolve([250, 350])
            });
    }
    )
}

function installCardsSize(width, height) {
    const styleElement = document.createElement('style');
    styleElement.textContent = ':root {\n' +
        '    --mo-card-width: ' + width + 'px;\n' +
        '    --mo-card-height: ' + height + 'px;\n' +
        '}';

    document.documentElement.appendChild(styleElement);
}

function installStyles(theme) {
    const linkElementColors = document.createElement('link');
    linkElementColors.rel = 'stylesheet';

    logMo("theme:" + theme)
    const timestamp = '?v=' + new Date().getTime();

    if (theme === 'dark') {
        logMo('installing dark theme')
        linkElementColors.href = 'file=extensions/sd-model-organizer/styles/colors-dark.css' + timestamp;
    } else {
        logMo('installing light theme')
        linkElementColors.href = 'file=extensions/sd-model-organizer/styles/colors-light.css' + timestamp;
    }

    document.head.appendChild(linkElementColors);

    const linkElementStyles = document.createElement('link');
    linkElementStyles.rel = 'stylesheet';
    linkElementStyles.href = 'file=extensions/sd-model-organizer/styles/styles.css' + timestamp;
    document.head.appendChild(linkElementStyles);
}

onUiLoaded(function () {
    logMo("UI loaded")
    const homeTab = findElem('mo_home_tab')
    const intersectionObserver = new IntersectionObserver((entries) => {
        if (entries[0].intersectionRatio > 0) invokeHomeInitialStateLoad();
    });
    intersectionObserver.observe(homeTab);

    getTheme()
        .then(data => {
            installStyles(data)
        })

    getCardsSize()
        .then(size => {
            installCardsSize(size[0], size[1])
        })
})

let organizerTab = null;
let lastTabName = 'txt2img';
let finishedSearching = false;
const inputEvent = new Event('input', { 'bubbles': true, "composed": true });
const changeEvent = new Event('change', { 'bubbles': true, "composed": true });
// Extra networks tab integration
// Huge thanks to https://github.com/CurtisDS/sd-model-preview-xd/tree/main for how to do this
onUiUpdate(function () {

    // get the organizer tab
    let tabs = gradioApp().querySelectorAll("#tabs > div:first-of-type button");
    if (typeof tabs != "undefined" && tabs != null && tabs.length > 0) {
        tabs.forEach(tab => {
            if (tab.innerText == "Model Organizer") {
                organizerTab = tab;
            }
        });
    }

    // Get
    let thumbCards = gradioApp().querySelectorAll("#txt2img_extra_tabs .card:not([organizer-hijack]), #img2img_extra_tabs .card:not([organizer-hijack])");
    if (typeof thumbCards != "undefined" && thumbCards != null && thumbCards.length > 0) {
        thumbCards.forEach(card => {
            let buttonRow = card.querySelector('.button-row');
            // the name of the model is stored in a span beside the .additional div
            //let modelName = card.getAttribute('data-name');
            let modelName = card.getAttribute('data-sort-name');

            // Button to open organizer
            let organizerBtnOpen = document.createElement("div");
            organizerBtnOpen.className = "organizer-buttonOpen card-button info";
            organizerBtnOpen.title = "Go To Record";
            organizerBtnOpen.onclick = function (event) {
                addRecordClick(event, modelName);
            };
            buttonRow.prepend(organizerBtnOpen);

            // we are finished so add the hijack attribute so we know not we don't need to do this card again
            card.setAttribute("organizer-hijack", true);
        });
    }
})

// Switch to Organizer Tab
function switchToOrganizerTab(event, name) {
    event.stopPropagation();
    event.preventDefault();

    var tabs = gradioApp().querySelectorAll('#tab_txt2img, #tab_img2img');
    if (typeof tabs != "undefined" && tabs != null && tabs.length > 0) {
        tabs.forEach(tab => {
            styleattr = tab.getAttribute('style');
            if (styleattr.includes('block')) {
                lastTabName = tab.id.substring(4);
            }
        });
    }


    organizerTab.click();
    organizerTab.dispatchEvent(inputEvent);

    var statebox = gradioApp().querySelector("#mo-home-state-box");
    statebox.dispatchEvent(changeEvent);

    var accordion = gradioApp().querySelector("#model_organizer_accordion");
    var labelWrap = accordion.querySelector('.label-wrap');

    if (!labelWrap.classList.contains('open')) {
        labelWrap.click();
        labelWrap.dispatchEvent(inputEvent);
    }

    var searchArea = gradioApp().querySelector("#model_organizer_searchbox textarea");
    setTimeout((event) => {
        searchArea.value = name;
        searchArea.dispatchEvent(inputEvent);
    }, 150);
}

function addRecordClick(event, name) {
    switchToOrganizerTab(event, name);

    //Find the card and click add button
    setTimeout((event) => {
        var recordButtons = gradioApp().querySelectorAll('#organizer_record_table button.mo-btn.mo-btn-success, #organizer_record_card_grid button.mo-btn.mo-btn-success');
        if (recordButtons.length == 1) {
            recordButtons[0].click();
        }
    }, 400);

}

function fillPrompt(recordid) {
    logMo('Loading record info for id: ' + recordid)
    const navObj = {
        screen: "record_info",
        record_info_id: recordid,
        token: generateUUID(),
        backstack: populateBackstack()
    };
    deliverNavObject(navObj)

    var timer = setInterval(() => {
        record_data = gradioApp().querySelector('#mo_record_info_nav_box textarea');

        if (record_data == null) return;
        var terminate = false;
        var jsdata = record_data.value;
        var jsdata = jsdata.replace(/'/g, '"').replace(/"checkpoint": True/mg, '"checkpoint": true').replace(/"checkpoint": False/mg, '"checkpoint": false');
        recordInfo = JSON.parse(jsdata);
        if (recordInfo.hasOwnProperty("id") && recordInfo["id"] === recordid) {
            var pos = "";
            var neg = "";
            if (recordInfo.hasOwnProperty('positive_prompts')) {
                pos = recordInfo['positive_prompts'];
                terminate = true;
            }
            if (recordInfo.hasOwnProperty('negative_prompts')) {
                neg = recordInfo['negative_prompts'];
                terminate = true;
            }
            if (recordInfo.hasOwnProperty('checkpoint') && recordInfo['checkpoint']) {
                selectCheckpoint(recordInfo['positive_prompts']);
                terminate = true;
            } else {
                if (pos !== "") {
                    cardClicked(lastTabName, pos, "", false);
                }
                if (neg !== "") {
                    cardClicked(lastTabName, "", neg, true);
                }
            }
        }
        if (terminate) {
            clearInterval(timer);
        }
    }, 100)

    return []
}
