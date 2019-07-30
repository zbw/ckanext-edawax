/*
 * Small script to check if there's a DOI error and make changes to page
*/

function checkError(){
    var message_container = document.getElementsByClassName('flash-messages');
    var messages = message_container[0].childNodes;

    if (messages.length > 1){
        return true;
    } else {
        return false;
    }
}

function createError(){
    var new_element = document.createElement('span');
    new_element.className = "error-block";
    new_element.innerHTML = 'DOI is invalid. Format should be: 10.xxxx/xxxx';

    return new_element;
}


if (checkError()){
    var pub = document.getElementById('publication');
    var target = pub.childNodes[1].childNodes[7].childNodes[1];

    target.className += " error";
    target = target.childNodes[3];

    var new_element = createError();
    target.appendChild(new_element);
}
