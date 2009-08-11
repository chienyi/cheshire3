/*
 // Script:	searchForm.js
 // Version:	0.08
 // Description:
 //          JavaScript functions used in the Cheshire3 EAD search/retrieve and display interface
 //          - part of Cheshire for Archives v3.x
 //
 // Language:  JavaScript
 // Author:    John Harrison <john.harrison@liv.ac.uk>
 // Date:      17 February 2009
 //
 // Copyright: &copy; University of Liverpool 2005-2009
 //
 // Version History:
 // 0.01 - 03/08/2006 - JH - Search form DOM manipulation functions pasted in from previous script for easier error tracking etc.
 // 0.02 - 24/10/2006 - JH - Additions for adding/removing phrase option to relation drop-down when necessary
 // 0.03 - 11/12/2006 - JH - Mods for compatibility with IE7
 //							- get elements by id rather than name wherever possible
 //							- use innerHTML to setup radio buttons
 // 0.04 - 14/12/2006 - JH - Search form state maintained in cookie. Reset function added.
 // 0.05 - 25/01/2007 - JH - Muchos new stuff in anticipation of date searching
 // 0.06 - 19/12/2007 - JH - Multiple indexes specified in fieldidx
 // 0.07 - 26/09/2008 - JH - Bug fixed in createClause (title index not being assigned correct relations) ln 126
 // 0.08 - 17/02/2009 - JH - Functions re-orders so not referenced before declared
 */

//var indexList = new Array('cql.anywhere||dc.description||dc.title|||Keywords', 'dc.title|||Titles', 'dc.date|||Dates', 'dc.creator|||Creators', 'dc.identifier|||Ref. Number', 'dc.subject|||Subjects', 'bath.name|||Names', 'bath.personalName|||&nbsp;&nbsp;Personal Names', 'bath.corporateName|||&nbsp;&nbsp;Corporate Names', 'bath.geographicName|||&nbsp;&nbsp;Geographical Names', 'bath.genreForm|||Genre');

var kwRelationList = new Array('all/relevant/proxinfo|||All', 'any/relevant/proxinfo|||Any');
var exactRelationList = new Array('exact/relevant/proxinfo|||Exactly');
//var proxRelationList = new Array('=/relevant/proxinfo|||Phrase');
var proxRelationList = new Array();
var dateRelationList = new Array('%3C|||Before', '%3E|||After', 'within/relevant/proxinfo|||Between', 'encloses/relevant/proxinfo|||Spans...');

//var relSelectPhraseElement = document.createElement('option');
//relSelectPhraseElement.value = '=/relevant/proxinfo';
//relSelectPhraseElement.appendChild(document.createTextNode('Phrase'));

function updateSelects(current) {
    var idxSelect = document.getElementById('fieldidx' + current);
    var relSelect = document.getElementById('fieldrel' + current);
    if (!idxSelect || !relSelect || !idxSelect.options || !relSelect.options) {
        return;
    }
    relSelect.options[relSelect.selectedIndex].selected = false;
    var iSelIdx = idxSelect.selectedIndex;
    var rSelIdx;
    var idxName = idxSelect.options[iSelIdx].value;
    var parts = idxName.split('.');
    var subName = parts[parts.length - 1];

    // complex conditional to decide available relations
    var relationList = new Array();

    var isDate = (/^date/i.test(subName) || /date$/i.test(subName));
    var isIdentifier = (/identifier$/i.test(subName) || /ID$/.test(subName));

    if (isIdentifier) {
        rSelIdx = 2;	// Identifiers are always "and" by default
    } else {
        rSelIdx = 0;
    }

    if (isIdentifier) {
        relationList = kwRelationList.concat(exactRelationList);
    } else if (isDate) {
        relationList = dateRelationList.concat(exactRelationList);
    } else {
        relationList = kwRelationList.concat(exactRelationList.concat(proxRelationList));
    }

    // now replace existing relation select element
    relSelect.parentNode.insertBefore(createSelect('fieldrel' +
                                                   current, relationList, rSelIdx), relSelect);
    relSelect.parentNode.removeChild(relSelect);
}

function updateIndexes() {
    var node;
    for (var i = 1; (node = document.getElementById('fieldidx' + i)) !=
                    null; i++) {
        while (node.hasChildNodes()) {
            node.removeChild(node.firstChild);
        }
        sel = createSelect('tmp', indexList, 0);
        while (sel.hasChildNodes()) {
            node.appendChild(sel.firstChild);
        }
    }
}

function addSearchClause(current, boolIdx, clauseState) {
    if (!document.getElementById || !document.createElement) {
        return;
    }
    //var form = document.getElementsByName('searchform')[0]
    var insertHere = document.getElementById('addClauseP');
    if (current > 0) {
        newBool = createBoolean(current, boolIdx);
        insertHere.parentNode.insertBefore(newBool, insertHere);
        //form.insertBefore(boolOp, form.childNodes[insertBeforePosn])
    }
    current++;
    newClause = createClause(current, clauseState);
    insertHere.parentNode.insertBefore(newClause, insertHere);
    //form.insertBefore(clause, form.childNodes[insertBeforePosn+1])
    document.getElementById('addClauseLink').href =
    'javascript:addSearchClause(' + current + ');';
}

function createBoolean(current, selIdx) {
    /* radio buttons cannot be created by DOM for IE - use innerHTML instead */
    if (!selIdx) {
        selIdx = 0;
    }
    var pElem = document.createElement('p');
    pElem.setAttribute('id', 'boolOp' + current);
    pElem.setAttribute('class', 'boolOp');
    var boolList = new Array('and/relevant/proxinfo', 'or/relevant/proxinfo', 'not');
    var inputs = new Array();
    for (var i = 0; i < boolList.length; i++) {
        var val = new String(boolList[i]);
        var shortName;
        if (val.indexOf('/') > 0) {
            shortName = val.substring(0, val.indexOf('/'));
        } else {
            shortName = val;
        }
        inputs[i] =
        '<input type="radio" name="fieldbool' + current + '" value="' + val +
        '" id="fieldbool' + current + '-' + shortName + '"';
        if (i == selIdx) {
            inputs[i] += ' checked="checked"';
        }
        inputs[i] +=
        '/><label for="fieldbool' + current + '-' + shortName + '">' +
        shortName.toUpperCase() + '&nbsp;&nbsp;</label>';
    }
    pElem.innerHTML = inputs.join('\n');
    return pElem;
}

function createSelect(name, optionList, selIdx) {
    // set 1st option as selected by default
    if (!selIdx) {
        selIdx = 0;
    }
    var selectElem = document.createElement('select');
    selectElem.id = name;
    selectElem.name = name;
    for (var i = 0; i < optionList.length; i++) {
        var optionData = optionList[i].split('|||');
        var optionElem = document.createElement('option');
        optionElem.value = optionData[0];
        optionElem.innerHTML = optionData[1];

        if (i == selIdx) {
            optionElem.selected = 'selected';
        }
        selectElem.appendChild(optionElem);
    }
    return selectElem;
}

function createClause(current, clauseState) {
    if (!clauseState) {
        clauseState = '0,0,';
    }
    var parts = clauseState.split(',');
    var pElem = document.createElement('p');
    pElem.setAttribute('id', 'searchClause' + current);
    pElem.setAttribute('class', 'searchClause');
    // index select
    var iSelIdx = parts.shift();
    var idxSelect = createSelect('fieldidx' + current, indexList, iSelIdx);
    idxSelect.onchange = new Function('updateSelects(' + current + ');');
    pElem.appendChild(idxSelect);
    pElem.appendChild(document.createTextNode(' for '));
    // relation select
    var rSelIdx = parts.shift();
    // complex conditional to decide available relations
    var relationList = new Array();
    if (iSelIdx != 2) {
        relationList = kwRelationList;
    }
    if (iSelIdx > 0) {
        relationList = relationList.concat(exactRelationList);
    }
    if (iSelIdx < 2) {
        relationList = relationList.concat(proxRelationList);
    }
    if (iSelIdx == 2) {
        relationList = relationList.concat(dateRelationList);
    }
    pElem.appendChild(createSelect('fieldrel' +
                                   current, relationList, rSelIdx));
    // text input
    var inputElem = document.createElement('input');
    inputElem.name = 'fieldcont' + current;
    inputElem.id = 'fieldcont' + current;
    inputElem.type = 'text';
    inputElem.size = 45;
    // last entered value
    inputElem.value = parts.join(',');
    pElem.appendChild(inputElem);
    return pElem;
}

function removeClause(current) {
    var pElem = document.getElementById('boolOp' + (current - 1));
    if (pElem) {
        pElem.parentNode.removeChild(pElem);
    }
    pElem = document.getElementById('searchClause' + current);
    pElem.parentNode.removeChild(pElem);
    document.getElementById('addClauseLink').href =
    'javascript:addSearchClause(' + current + ');';
}

function resetForm(formid) {
    if (typeof formid == "undefined") {
        formid = "searchform";
    }
    var i = 1;
    while (document.getElementById('searchClause' + i)) {
        removeClause(i);
        i++;
    }
    addSearchClause(0);
    document.getElementById('addClauseLink').href =
    'javascript:addSearchClause(1);';
    setCookie(formid, '');
}

function formToString(form) {
    var i = 0;
    var fields = new Array();
    var bools = new Array();
    while (document.getElementById('fieldcont' + (i + 1)) &&
           document.getElementById('fieldcont' + (i + 1)).value != "") {
        bools[i] = 0;
        if (i > 0) {
            var boolgrp = document.getElementsByName('fieldbool' + i);
            //while (!boolgrp[0].value) {boolgrp = boolgrp.slice(1);}
            for (var j = 0; j < boolgrp.length; j++) {
                if (boolgrp[j].checked) {
                    bools[i] = j;
                }
            }
        }
        i++;
        var idx = document.getElementById('fieldidx' + i).selectedIndex;
        var rel = document.getElementById('fieldrel' + i).selectedIndex;
        var cont = document.getElementById('fieldcont' + i).value;
        fields[i - 1] = new Array(idx, rel, cont).join();
    }
    var stateString = fields.join('||') + '<CLAUSES|BOOLS>' + bools.join('||');
    return stateString;
}

function formFromString(s) {
    var parts;
    if (s && s.length > 0) {
        parts = s.split('<CLAUSES|BOOLS>');
    } else {
        parts = new Array();
    }
    if (parts.length == 2) {
        var clauseList = parts[0].split('||');
        var boolList = parts[1].split('||');
        for (var i = 0; i < clauseList.length; i++) {
            addSearchClause(i, boolList[i], clauseList[i]);
        }
    } else {
        // no state - initialise empty search form
        addSearchClause(0);
    }
}