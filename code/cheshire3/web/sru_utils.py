import time, httplib, urllib2
from lxml import etree
from lxml import objectify

class SruObject:
    """ Abstract class for objectifying SRU XML
    ZSI attrs: name, typecode
    """
    
    tree = None
    
    def __dir__(self):
        attrlist = dir(self) 
        attrlist.extend(['name', 'typecode'])
        attrlist.sort()
        return  attrlist
    
    def __init__(self, node):
        self.tree = node
    
    def __getattr__(self, name):
        # avoid command line repr wierdness
        if name == '__repr__':
            raise AttributeError
        elif name == 'name':
            return self.tag[self.tag.find('}')+1:]
        elif name =='typecode':
            return

        return getattr(self.tree, name)    

    def __str__(self):
        return objectify.dump(self.tree)
        #return etree.tostring(self.tree)
        
    #- end SruObject ----------------------------------------------------------

class SruRecord(SruObject):
    """ Thin wrapper for records returned in SRU responses. 
    Note: Not the same as a Cheshire3 Record - although the recordData could be used to construct one...
    ZSI attrs (additional): inline, recordData, recordPacking, recordPosition, recordSchema
    """
    
    def __dir__(self):
        attrlist = SruObject.__dir__(self) 
        attrlist.extend(['inline', 'recordData', 'recordPacking', 'recordPosition', 'recordSchema'])
        attrlist.sort()
        return  attrlist
    
    def __getattr__(self, name):
        if name == 'recordData':
            return SruRecordData(self.tree.recordData.getchildren()[0])

        return SruObject.__getattr__(self, name)

    #- end SruRecord ----------------------------------------------------------

class SruRecordData(SruObject):
    
    def __dir__(self):
        attrlist = SruObject.__dir__(self) 
        attrlist.extend(['toxml'])
        attrlist.sort()
        return  attrlist
    
    def __getattr__(self, name):
        if name == 'id':
            try:
                return self.tree.attrib['id']
            except KeyError:
                pass

        return SruObject.__getattr__(self, name)
    
    def toxml(self):
        return etree.tostring(self.tree)
    
    #- end SruRecordData ------------------------------------------------------

class SruResponse(SruObject):
    """ Abstract class for SRU responses
    ZSI attrs (additional): diagnostics, extraResponseData, version
    """
    
    def __dir__(self):
        attrlist = SruObject.__dir__(self) 
        attrlist.extend(['diagnostics', 'extraResponseData', 'version'])
        attrlist.sort()
        return  attrlist
    
    def __getattr__(self, name):
        if name == 'diagnostics':
            try:
                diags = SruObject.__getattr__(self, name) 
                return [ el for el in diags.iterchildren(tag='{http://www.loc.gov/zing/srw/diagnostic/}diagnostic') ]
            except AttributeError:
                return []

        return SruObject.__getattr__(self, name)

    #- end SruResponse --------------------------------------------------------
    
class ExplainResponse(SruResponse):
    """ Thin wrapper for SRU Explain Response
    ZSI attrs (additional): echoedExplainRequest, record
    """ 
    
    def __dir__(self):
        attrlist = SruResponse.__dir__(self) 
        attrlist.extend(['echoedExplainRequest', 'record'])
        attrlist.sort()
        return  attrlist
    
    def __getattr__(self, name):
        if name == 'record':
            return SruRecord(self.tree.record)
        
        return SruResponse.__getattr__(self, name)
            
    def __str__(self):
        return objectify.dump(self.tree)
        #return "%s:\n    Version: %s\n    Record (presence of): %i\n    Diagnostics: %s\n    ExtraResponseData: %s" % (self.__class__.__name__, self.version, self.record <> None, repr(self.diagnostics), repr(self.extraResponseData))
        
    #- end ExplainResponse ----------------------------------------------------

class SearchRetrieveResponse(SruResponse):
    """ Thin wrapper for SRU SearchRetrieve Response
    ZSI attrs (additional): echoedSearchRetrieveRequest, numberOfRecords, records, nextRecordPosition, resultSetId, resultSetIdleTime
    """
    
    def __dir__(self):
        attrlist = SruResponse.__dir__(self) 
        attrlist.extend(['echoedSearchRetrieveRequest', 'nextRecordPosition', 'numberOfRecords', 'records', 'resultSetId', 'resultSetIdleTime'])
        attrlist.sort()
        return  attrlist
           
    def __getattr__(self, name):
        if name == 'records':
            return [SruRecord(el) for el in self.tree.records.record]
    
        return SruResponse.__getattr__(self, name)
        
    #- end SearchRetrieveResponse ---------------------------------------------
    
class ScanResponse(SruResponse):
    """ Thin wrapper for SRU Scan Response
    ZSI attrs (additional): echoedScanRequest, terms
    """
    def __dir__(self):
        attrlist = SruResponse.__dir__(self) 
        attrlist.extend(['echoedscanRequest', 'terms'])
        attrlist.sort()
        return  attrlist
    
    def __getattr__(self, name):
        if name == 'terms':
            try:
                return [el for el in self.tree.terms.term]
            except AttributeError:
                return []

        return SruResponse.__getattr__(self, name)
    
    #- end ScanResponse -------------------------------------------------------


def fetch_data(myUrl, tries=3):
    req = urllib2.Request(url=myUrl)
    for x in range(tries):
        try:
            f = urllib2.urlopen(req)
        except (urllib2.URLError, httplib.BadStatusLine):
            # problem accessing remote service
            time.sleep(1)
            continue
        else:
            data = f.read()
            f.close()
            return data
        
    return None


# functions to fetch and return a parsed response object when given a URL
def get_explainResponse(url):
    data = fetch_data(url)
    if data:
        tree = objectify.fromstring(data)
        return ExplainResponse(tree)
        

def get_searchRetrieveResponse(url):
    data = fetch_data(url)
    if data:
        tree = objectify.fromstring(data)
        return SearchRetrieveResponse(tree)

    
def get_scanResponse(url):
    data = fetch_data(url)
    if data:
        tree = objectify.fromstring(data)
        return ScanResponse(tree)