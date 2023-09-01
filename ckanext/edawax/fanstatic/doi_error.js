/*
 * Small script to check if there's a DOI error and make changes to page
*/

function checkErrorTop(){
    /* Error message when trying to publish */
    var message_container = document.getElementsByClassName('flash-messages');
    var messages = message_container[0].childNodes;

    if (messages.length > 1){
        return true;
    } else {
        return false;
    }
}

function checkErrorMid(){
    /* Error message trying to update with a bad DOI */
    var message_container = document.getElementsByClassName('error-explanation');
    var list = message_container[0].childNodes[3];
    var item = list.childNodes[1];

    if (item){
        return true;
    }
    return false;

}


function createError(){
    var new_element = document.createElement('span');
    new_element.className = "error-block";
    new_element.innerHTML = 'DOI is invalid. Format should be: 10.xxxx/xxxx';

    return new_element;
}

function createLink(){
    var new_element = document.createElement('a');
    new_element.href= '#doi';
    new_element.style.color = ' blue';
    //new_element.innerHTML = 'Jump to field.';
    new_element.innerHTML = window.location.href;

    return new_element;
}


if (checkErrorTop()){
    var pub = document.getElementById('publication');
    var target = pub.childNodes[1].childNodes[7].childNodes[1];

    target.className += " error";
    target = target.childNodes[3];

    var new_element = createError();
    target.appendChild(new_element);
}


if (checkErrorMid()){
    var message_container = document.getElementsByClassName('error-explanation');
    var list = message_container[0].childNodes[3];
    var item = list.childNodes[1];

    item.appendChild(createLink());
}
