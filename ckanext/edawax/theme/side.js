/*
 * Script for determining which side an element should float on
 */

function determineSide(element){
    // Get halfway point of screen
    var width = window.screen.width;
    var target = width / 2;

    var rect = element.getBoundingClientRect();
    var point = rect.left;

    if (point < target){
        return "left";
    }
    return "right";
}


function setFloat(element, side){
    if (side == 'left'){
        element.classList.add('left-side');
    } else {
        element.classList.add('right-side');
    }
}


function checkElements(){
    var elements = document.getElementsByTagName('section');

    for (var i=0; i<elements.length; i++){
        console.log('####');
        console.log(elements[i]);
        /* tag section is contained in div.tag_section */
        if (elements[i].classList.length == 0){
            var target_element = elements[i].childNodes[1];
        /* the description and image are in div.top-info */
        } else if (elements[i].classList[0] == 'module-content'){
            var target_element = elements[i].childNodes[1];
        } else {
            var target_element = elements[i];
        }
        console.log(target_element);
        var side = determineSide(target_element);
        setFloat(target_element, side);
    }
}


if (window.screen.width < 0){
    checkElements();
}
