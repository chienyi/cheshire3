from baseObjects import ResultSet, ResultSetItem, Index
from PyZ3950 import CQLParser
import math, types, sys

from xml.sax import ContentHandler, make_parser, parseString as saxParseString, ErrorHandler, InputSource as SaxInput
import cStringIO as StringIO
from xml.sax.saxutils import escape, unescape
import utils
import cPickle

class DeserializationHandler(ContentHandler):
    items = []
    item = None
    set = None
    session = None
    currContent = ""
    

    def reinit(self, session, set):
        self.currContent = ""
        self.session = session
        self.set = set
        self.items = []
        self.item = None
        
    def startElement(self, name, attrs):
        if name == "item":
            self.item = SimpleResultSetItem(self.session)
            
    def endElement(self, name):
        c = self.currContent
        if name == "queryFreq":
            self.set.queryFreq = long(c)
        elif name == "queryTerm":
            self.set.queryTerm = c
        elif name == "totalOccs":
            self.set.totalOccs = long(c)
        elif name == "totalRecs":
            self.set.totalRecs = long(c)
        elif name == "termWeight":
            self.set.termWeight = float(c)
        elif name == "queryPositions" and c:
            if len(c) > 1:
                self.set.queryPositions = cPickle.loads(str(c))
        elif name == "item":
            self.set.append(self.item)
        elif name == "recStore":
            self.item.recordStore = c
        elif name == "id":
            if c.isdigit():
                self.item.id = long(c)
            else:
                self.item.id = c
        elif name == "weight":
            self.item.weight = float(c)
        elif name == "scaledWeight":
            self.item.scaledWeight = float(c)
        elif name == "occs":
            self.item.occurences = long(c)
        elif name == "database":
            self.item.database = c
        elif name == "proxInfo" and c:
            if len(c) > 1:
                self.item.proxInfo = cPickle.loads(str(c))
        self.currContent = ""

    def characters(self, text):
        self.currContent += unescape(text)


localParser = make_parser()
localParser.setErrorHandler(ErrorHandler())
localInput = SaxInput()
localHandler = DeserializationHandler()
localParser.setContentHandler(localHandler)


class RankedResultSet(ResultSet):

    #    def _sumWeights(self, items, n):
    #        item = items[0]
    #        item.weight = sum([x.weight for x in items])
    #        return item
        
    #    def _meanWeights(self, items, n):
    #        item = items[0]
    #        item.weight = sum([x.weight for x in items])
    #        item.weight = item.weight / n
    #        return item
    
    def _sumWeights(self, items, n):
        item = items[0]
        #item.weight = sum([x.weight for x in items])
        item.weight = sum([x.weight for x in items if (x.weight <> 0.5)])
        return item
        
    def _meanWeights(self, items, n):
        item = items[0]
        #item.weight = sum([x.weight for x in items])
        #item.weight = item.weight / n
        trueWeightedItems = [x.weight for x in items if (x.weight <> 0.5)]
        item.weight = sum(trueWeightedItems)
        item.weight = item.weight / len(trueWeightedItems)
        return item


    def _normWeights(self, items, n):
        for i in items:
            i.weight = i.weight * (i.resultSet.minWeight / i.resultSet.maxWeight)
        return self._meanWeights(items, n)

    def  _cmbzWeights(self, a, b):
        a.weight = a.weight * (self.minWeight / self.maxWeight)
        if b:
            b.weight = b.weight * (self.minWeight / self.maxWeight)
            a.weight = (a.weight + b.weight) *  2.0
        else:
            a.weight = a.weight / 2.0

    def _nprvWeights(self, a, b):
        a.weight = a.weight * (self.minWeight / self.maxWeight)
        if b:
            b.weight = b.weight * (self.minWeight / self.maxWeight)
            a.weight = (a.weight + b.weight) *  2.0
        else:
            # Leave high ranking ones high
            rlen = len(a.resultSet._list)
            if (( rlen > 150 and item.resultSetPosition > 100)
                or (rlen < 150 and item.resultSetPosition > rlen/2)):
                a.weight = a.weight  / 2.0

    def _pivotWeights(self, a, b):
        # Determine which item is component set, and which item is from document set
        # If the component's parent document's id is the same as the one in the
        # full document list, then adjust

        # Normalise min/max as above
        # Pivot default is 0.7, but allow override
        # (Pivot * documentScore) + ((1-pivot) * componentScore)

        # If not in the list then just ((1-pivot) * componentScore)

        pass

    
class SimpleResultSet(RankedResultSet):
    _list = []

    id = ""
    termid = -1
    totalOccs = 0
    totalRecs = 0
    expires = 0
    index = None
    queryTerm = ""
    queryFreq = 0
    queryFragment = None
    queryPositions = []
    relevancy = 0
    maxWeight = 0
    minWeight = 0
    termWeight = 0.0
    recordStore = ""
    recordStoreSizes = 0

    def __init__(self, session, data=[], id="", recordStore=""):
        self._list = data
        self.id = id
        self.recordStore = recordStore
        self.recordStoreSizes = 0

    def __getitem__(self, k):
        return self._list[k]

    def __len__(self):
        return len(self._list)

    def fromList(self, data):
        self._list = data

    def serialise(self, session):
        # Turn into XML
        xml = ['<resultSet>']
        xml.append('<queryTerm>%s</queryTerm><queryFreq>%s</queryFreq><queryPositions>%s</queryPositions><termWeight>%s</termWeight>' % (self.queryTerm, self.queryFreq, escape(cPickle.dumps(self.queryPositions)), self.termWeight))
	xml.append('<totalRecs>%s</totalRecs><totalOccs>%s</totalOccs>' % (self.totalRecs, self.totalOccs))
	xml.append('<items>')
        for item in self:
            if type(item.id) in types.StringTypes:
                docid = escape(item.id)
            else:
                docid = str(item.id)
            xml.append("<item><recStore>%s</recStore><id>%s</id><occs>%s</occs><weight>%s</weight><scaledWeight>%s</scaledWeight><proxInfo>%s</proxInfo><database>%s</database></item>" % (item.recordStore,
              docid,
              item.occurences,
              item.weight,
              item.scaledWeight,
              escape(cPickle.dumps(item.proxInfo)),
              item.database))
        xml.append('</items>')
        xml.append('</resultSet>')
        return ''.join(xml)

    def deserialise(self, session, data):
        self._list = []
        localHandler.reinit(session, self)
        localInput.setByteStream(StringIO.StringIO(data))
        localParser.parse(localInput)
        return None


    def append(self, item):
        item.resultSet = self
        item.resultSetPosition = len(self._list)
        self._list.append(item)

    def extend(self, itemList):
        for i in itemList:
            self.append(i)

    def _lrAssign(self, session, others, clause, cql, db):
            if (db):
                totalDocs = db.totalItems
                if totalDocs == 0:
                    raise ValueErorr("No documents in database?")
            else:
                # Uhoh
                raise NameError("Database not supplied to relevancy algorithm")

            # William S Cooper proposes:
            constants = [-3.7, 1.269, -0.31, 0.679, -0.0674, 0.223, 2.01]

            # Ray R Larson proposes:
            constants = [-3.7, 1.269, -0.31, 0.679, -0.021, 0.223, 4.01]

            # Index Configuration proposes:
            idx = db.protocolMaps['http://www.loc.gov/zing/srw/'].resolveIndex(session, clause)
            if (idx):
                for x in range(7):
                    temp = idx.get_setting(session, 'lr_constant%d' % x)
                    if (temp):
                        constants[x] = float(temp)

            # Query proposes:
            relSetUri = "info:srw/cql-context-set/2/relevance-1.0"
            for m in cql.modifiers:
                # Already been pinged for resolve()
                if (m.type.prefixURI == relSetUri):
                    if m.type.value[:5] == "const":
                        try:
                            constants[int(m.type.value[5])] = float(m.value)
                        except ValueError:
                            # Invalid literal for float()
                            pass
                        except IndexError:
                            # list index out of range
                            pass

            sumLogQueryFreq = 0.0
            sumQueryFreq = 0
            sumIDF = 0.0

            # Sort rss by length

            # Each rs represents one unique word in query
            for rs in others:
                sumLogQueryFreq += math.log(rs.queryFreq)
                sumQueryFreq += rs.queryFreq
                n = len(rs)
                if n:
                    rs.idf = math.log(totalDocs / float(n))
            x2 = math.sqrt(sumQueryFreq)

            # resultSets will be sorted by item already
            # Step through all concurrently

            tmpList =  []
            cont = 1
            oidxs = range(1,len(others))
            nors = len(others)
            positions = [0] * nors
            all = cql.value in ['all', 'and', '=', 'prox', 'adj']
            maxWeight = -1
            minWeight = 9999999999

            while cont:                
                items = [others[0][positions[0]]]
                rspos = [0]
                for o in oidxs:
                    nitem = others[o][positions[o]]
                    if nitem == items[0]:
                        items.append(nitem)
                        rspos.append(o)
                    elif nitem < items[0]:
                        if all:
                            # skip until equal or greater
                            positions[o] += 1
                            while others[o][positions[o]] < items[0]:
                                positions[o] += 1
                        else:
                            items = [nitem]
                            rspos = [o]
                for r in rspos:
                    positions[r] += 1

                while others and positions[0] == len(others[0])-1:
                    others.pop(0)
                    positions.pop(0)
                if not others:
                    cont = 0
                if all and len(items) < nors:
                    continue

                sumLogDAF = sum(map(math.log, [x.occurences for x in items]))
                sumIdx = sum([x.resultSet.idf for x in items])

                x1 = sumLogQueryFreq / float(n)
                x3 = sumLogDAF / float(n)
                x5 = sumIDF / float(n)
                x6 = math.log(float(n))
                try:
                    recStore = recStores[item.recordStore]
                except:
                    db = session.server.get_object(session, session.database)
                    recStore = db.get_object(session, item.recordStore)
                    recStores[item.recordStore] = recStore
                doclen = recStore.fetch_recordMetadata(session, item.id, 'wordCount')
                x4 = math.sqrt(doclen)
                logodds = constants[0] + (constants[1] * x1) + (constants[2] * x2) + \
                          (constants[3] * x3) + (constants[4] * x4) + (constants[5] * x5) + \
                          (constants[6] * x6)
                item.weight= 0.75 * (math.exp(logodds) / (1 + math.exp(logodds)))
                tmplist.append(item)
                if item.weight > maxWeight:
                    maxWeight = item.weight
                elif item.weight < minWeight:
                    minWeight = item.weight

            self._list = tmplist
            self.minWeight = minWeight
            self.maxWeight = maxWeight
            self.relevancy = 1
            return 1

    def _coriAssign(self, session, others, clause, cql, db):
        if (db):
            totalDocs = float(db.totalItems)
            avgSize = float(db.meanWordCount)
            if not totalDocs or not avgSize:
                raise ValueError("0 documents in database")
        else:
                raise NameError("Database not supplied to relevancy algorithm")

        rsizes = clause.relation['recstoresizes']
        if not rsizes:
            rsizes = self.recordStoreSizes

        recStoreSizes = {}
            
        recStores = {}        
        for rs in others:
            matches = float(len(rs))
            if not matches:
                rs.minWeight = 1.0
                rs.maxWeight = -1.0
                continue
            I = math.log((totalDocs + 0.5) / matches) / math.log(totalDocs + 1.0)
            rs.minWeight = 1000000.0
            rs.maxWeight = -1.0
            for item in rs:
                df = float(item.occurences)
                recStore = recStores.get(item.recordStore, None)
                if not recStore:
                    recStore = db.get_object(session, item.recordStore)
                    recStores[item.recordStore] = recStore
                size = recStore.fetch_recordMetadata(session, item.id, 'wordCount')
                if rsizes:
                    avgSize = recStore.meanWordCount
                T = df / ( df + 50.0 + (( 150.0 * size) / avgSize))
                item.weight = 0.4 + (0.6 * T * I)
                if item.weight > rs.maxWeight:
                    rs.maxWeight = item.weight
                if item.weight < rs.minWeight:
                    rs.minWeight = item.weight
        return 0

    def _tfidfAssign(self, session, others, clause, cql, db):
        # w(i,j) = tf(i,j) * (log ( N / df(i)))
        if (db):
            totalDocs = float(db.totalItems)
            if not totalDocs:
                raise ValueError("0 documents in database")
        else:
                raise NameError("Database not supplied to relevancy algorithm")


        for rs in others:
            matches = float(len(rs))
            rs.minWeight = 10000000.0
            rs.maxWeight = -1.0
            for item in rs:
                weight = item.occurences * math.log(totalDocs / matches)
                item.weight = weight
                if rs.maxWeight < weight:
                    rs.maxWeight = weight
                if rs.minWeight > weight:
                    rs.minWeight = weight
        return 0

    def combine(self, session, others, clause, db=None):

        if (isinstance(clause, CQLParser.Triple)):
            cql = clause.boolean
        else:
            cql = clause.relation

        # XXX To Configuration
        relSetUri = "info:srw/cql-context-set/2/relevance-1.0"
        cqlSet = "info:srw/cql-context-set/1/cql-v1.1"

        relevancy = 0
        algorithm = "cori"
        combine = "mean"
        modType = ""
        for m in cql.modifiers:
            m.type.parent = clause
            m.type.resolvePrefix()
            if (m.type.prefixURI == relSetUri):
                # Relevancy info
                relevancy = 1
                if m.type.value == "algorithm":
                    algorithm = m.value
                elif m.type.value == "combine":
                    combine = m.value
            elif (m.type.prefixURI == cqlSet and m.type.value == "relevant"):
                # Generic 'relevancy please' request
                relevancy = 1

        # Check if any others are relevance ranked already and preserve
        if (not relevancy):
            for x in others:
                if (x.relevancy):
                    relevancy = 1
                    break
        pi = 0
        for m in cql.modifiers:
            if m.type.value == 'proxinfo':
                pi = 1
                break

        # sort result sets by length
        all = cql.value in ['all', 'and', '=', 'prox', 'adj']                
        if not cql.value in ['not', 'prox']:
            keys = [(len(x), x) for x in others]
            keys.sort(reverse=not all)
            others = [x for (key,x) in keys]    

        if (relevancy):
            self.relevancy = 1
            if (isinstance(cql, CQLParser.Relation)):
                fname = "_%sAssign" % algorithm
                if (hasattr(self, fname)):
                    fn = getattr(self, fname)
                else:
                    raise NotImplementedError
                finish = fn(session, others, clause, cql, db)
                if finish:
                    return self

        if len(others) == 1:
            if relevancy:
                # Just adding relevance to items?
                others[0].relevancy = 1
            return others[0]
        else:
            # Merge                    
            if relevancy:
                maxWeight = -1
                minWeight = 9999999999
                fname = "_%sWeights" % combine
                if (hasattr(self, fname)):
                    fn = getattr(self, fname)
                else:
                    raise NotImplementedError

            tmplist = []
            cont = 1
            oidxs = range(1,len(others))
            lens = [len(x) for x in others]
            if all and 0 in lens:
                # no point, just return empty result set
                return self
            nors = len(others)
            positions = [0] * nors
            cmpHash = {'<' : [-1],
                       '<=' : [-1, 0],
                       '=' : [0],
                       '>=' : [0, 1],
                       '>' : [1]}
            distance = 1
            unit = "word"
            comparison = "="
            ordered = 0
            if (cql.value == 'prox' and cql.modifiers):
                if (cql['unit']):
                    unit = cql['unit'].value
                if (cql['distance']):
                    distance = int(cql['distance'].value)
                    comparison = cql['distance'].comparison
                if cql['ordered']:
                    ordered = 1
            else:
                # for adj/=
                ordered = 1

            chitem = cmpHash[comparison]
            if unit == "word":
                proxtype = 1
            elif unit == "element" and distance == 0 and comparison == "=":
                proxtype = 2
            else:
                raise NotImplementedError()
            hasGetItemList = [hasattr(o, 'get_item') for o in others]
            while cont:                
                items = [others[0][positions[0]]]
                rspos = [0]
                for o in oidxs:
                    if o != -1:
                        if hasGetItemList[o]:
                            nitem = others[o].get_item(items[0])
                            if not nitem:
                                continue
                        else:    
                            try:
                                nitem = others[o][positions[o]]
                            except IndexError:
                                oidxs[o-1] = -1
                                continue
                            if nitem < items[0]:
                                if all or cql.value == 'not':
                                    # skip until equal or greater
                                    while True:
                                        positions[o] += 1
                                        if positions[o] >= lens[o] or others[o][positions[o]] >= items[0]:
                                            break
                                    if positions[o] != lens[o]:
                                        nitem = others[o][positions[o]]
                                else:
                                    items = [nitem]
                                    rspos = [o]
                                    continue
                        if nitem == items[0]:
                            items.append(nitem)
                            rspos.append(o)

                for r in rspos:
                    positions[r] += 1

                while others and positions[0] > len(others[0])-1:
                    others.pop(0)
                    positions.pop(0)
                    lens.pop(0)
                if not others or ((cql.value == 'not' or all) and len(others) != nors):
                    cont = 0
                if (all and len(items) < nors):
                    continue
                elif cql.value == 'not' and len(items) != 1:
                    continue
                elif cql.value in ["prox", 'adj', '=']:
                    # proxInfo is hash of (docid, recStore) to list of locations in record
                    # sort items by query position. Repeat set at each posn

                    if cql.value != "prox":
                        newitems = []
                        mqp = -1
                        for i in items:
                            i.queryTerm = i.resultSet.queryTerm
                            i.queryPositions = i.resultSet.queryPositions
                            for qp in i.queryPositions:
                                mqp = max(mqp, qp)
                        for idx in range(mqp+1):
                            for i in items:
                                if idx in i.queryPositions:
                                    newitems.append(i)
                                    break
                        items = newitems[:]
                    else:
                        #ffs
                        newitems = items[:]

                    litem = items.pop(0)
                    nomatch = 0                    

                    fullMatchLocs = []

                    while len(items):                        
                        ritem = items.pop(0)
                        matchlocs = []
                        for r in range(0,len(ritem.proxInfo),2):
                            relem = ritem.proxInfo[r]
                            rwpos = ritem.proxInfo[r+1]
                            for l in range(0, len(litem.proxInfo), 2):
                                if (proxtype == 1 and litem.proxInfo[l] == relem):
                                    wordDistance = rwpos - litem.proxInfo[l+1]
                                    if ordered and wordDistance < 0:
                                        # B is before A
                                        pass
                                    else:
                                        wordDistance = abs(wordDistance)
                                        c = cmp(wordDistance, distance)
                                        if (c in chitem):
                                            matchlocs.extend([relem, rwpos])
                                            fullMatchLocs.extend([litem.proxInfo[l], litem.proxInfo[l+1]])
                                            
                                elif proxtype == 2 and litem.proxInfo[l][0] == relem:
                                    matchlocs.extend([relem, rwpos])
                        if matchlocs:                                    
                            #Can't do this, as might have more later. a b c a would fail
                            ritem.proxInfo = matchlocs
                            litem = ritem                                
                        else:
                            # no match, break to next set of items
                            nomatch = 1
                            break
                    if nomatch:
                        continue
                    litem.proxInfo = fullMatchLocs
                    litem.proxInfo.extend(matchlocs)
                    items = [litem]
                    # items = newitems
                # do stuff on items to reduce to single representative
                if relevancy:
                    item = fn(items, nors)
                    if item.weight > maxWeight:
                        maxWeight = item.weight
                    if item.weight < minWeight:
                        minWeight = item.weight
                else:
                    item = items[0]
                if pi:
                    # copy proxInfo around
                    for o in items[1:]:
                        item.proxInfo.extend(o.proxInfo)                        
                tmplist.append(item)

            self._list = tmplist
            if relevancy:
                self.relevancy = 1
                self.minWeight = minWeight
                self.maxWeight = maxWeight
            return self

    def order(self, session, spec):
        # sort according to some spec
        # spec can be index, "docid", xpath, other?
        # XXX Need secondary sort specs

        l = self._list

        if not l:
            # don't try to sort empty set
            return

        if (isinstance(spec, Index) and spec.get_setting(session, 'sortStore')):
            # check pre-processed db
            istore = spec.get_path(session, 'indexStore')
            tmplist = [(istore.fetch_sortValue(session, spec, x), x) for x in l]
            tmplist.sort()
            self._list = [x for (key,x) in tmplist]
        elif isinstance(spec, Index):
            # Extract data as per indexing, MUCH slower
            recs = []
            storeHash = {}
            for r in l:
                store = r.recordStore
                o = storeHash.get(store, spec.get_object(session, store))
                storeHash[store] = o
                recs.append(o.fetch_record(session, r.id))
            tmplist = [(spec.extract_data(session, recs[x]), l[x]) for x in range(len(l))]
            tmplist.sort()
            self._list = [x for (key,x) in tmplist]
        elif (type(spec) == str and hasattr(self[0], spec)):
              # Sort by attribute of item
              tmplist = [(getattr(x, spec), x) for x in l]
              if spec  == 'docid':
                  tmplist.sort()
              else:
                  tmplist.sort(reverse=True)
              self._list = [x for (key, x) in tmplist]
        elif isinstance(spec, str):
            # XPath?
            raise NotImplementedError
        else:
            raise NotImplementedError

    def reverse(self, session):
        self._list.reverse()

    def scale_weights(self):
        minw = self.minWeight
        if self.maxWeight != minw:
            r = 1 / (self.maxWeight - minw)
        else:
            r = 1
        # faster than equivalent list comprehension!
        for rsi in self._list:
            rsi.scaledWeight = (rsi.weight - minw) * r

class SimpleResultSetItem(ResultSetItem):
    id = 0
    numericId = None
    recordStore = ""
    database = ""
    occurences = 0
    weight = 0.5
    scaledWeight = 0.5
    diagnostic = None
    proxInfo = []

    def __init__(self, session, id=0, recStore="", occs=0, database="", diagnostic=None, weight=0.5, resultSet = None, numeric=None):
        self.id = id
        self.recordStore = recStore
        self.occurences = occs
        self.weight = weight
        self.scaledWeight = 0.5
        self.database = database
        self.resultSet = resultSet
        self.proxInfo = []
        self.numericId = numeric

    def fetch_record(self, session):
        # return record from store
        if (session.server):
            # db = session.server.get_object(session, self.database)
            db = session.server.get_object(session, session.database)
            recStore = db.get_object(session, self.recordStore)
            rec = recStore.fetch_record(session, self.id)
            rec.resultSetItem = self
            return rec

    def __eq__(self, other):
        try:
            return self.id == other.id and self.recordStore == other.recordStore
        except:
            # not comparing two RSIs
            return False

    def __str__(self):
        return "%s/%s" % (self.recordStore, self.id)
    def __repr__(self):
        return "Ptr:%s/%s" % (self.recordStore, self.id)

    def __cmp__(self, other):
        # default sort by docid
        if self.numericId != None:
            if other.numericId != None:
                oid = other.numericId
            else:
                oid = other.id
            c = cmp(self.numericId, oid)
        else:
            c = cmp(self.id, other.id)
        if not c:
            return cmp(self.recordStore, other.recordStore)
        else:
            return c
        
    def __hash__(self):
        # Hash of recordstore + id
        return hash(str(self))


from utils import SimpleBitfield

class BitmapResultSet(ResultSet):
    bitfield = None
    currItems = None
    recordStore = None

    relevancy = 0
    termid = -1
    totalOccs = 0
    totalRecs = 0
    id = ""
    index = None
    queryTerm = ""
    queryFreq = 0
    queryFragment = None
    queryPositions = []
    relevancy = 0
    maxWeight = 0
    minWeight = 0

    def __init__(self, session, data=0, recordStore=None):
        if isinstance(data, SimpleBitfield):
            self.bitfield = data
        else:
            self.bitfield = SimpleBitfield(data)
        self.currItems = None
        self.recordStore = recordStore
        self.relevancy = 0

    def __getitem__(self, k):
        if self.currItems == None:
            self.currItems = self.bitfield.trueItems()            
        return SimpleResultSetItem(None, self.currItems[k], self.recordStore, 1)

    def __len__(self):
        return self.bitfield.lenTrueItems()

    def serialise(self, session):
        return str(self.bitfield)

    def deserialise(self, data):
        self.bitfield = SimpleBitfield(data)

    def get_item(self, item):
        try:
            if self.bitfield[item.id]:
                return item
        except IndexError:
            pass
        return None

    def combine(self, session, others, clause, db=None):
        if (isinstance(clause, CQLParser.Triple)):
            cql = clause.boolean
        else:
            cql = clause.relation
        v = cql.value

        # Check if all are bitmaps
        if v in ['=', 'exact', 'prox']:
            if len(others) == 1:
                return others[0]
            else:
                raise NotImplementedError()

        allbits = 1
        for o in others:
            if not hasattr(o, 'bitfield'):
                allbits = 0
                break

        if allbits:
            if (v in ['all', 'and']):            
                s = others[0].bitfield
                for o in others[1:]:
                    s.intersection(o.bitfield)
            elif (v in ['any', 'or', '>', '>=', '<', '<=']):
                s = others[0].bitfield
                for o in others[1:]:
                    s.union(o.bitfield)
            elif (v == 'not'):
                s = others[0].bitfield
                for o in others[1:]:
                    s.difference(o.bitfield)
            else:
                raise NotImplementedError()
            self.bitfield = s
        else:
            # XXX Merging Bitmap with non bitmap
            pass
        return self

    
    def order(self, spec):
        # Reorder a bitmap?!
        raise NotImplementedError()

    def retrieve(self, numReq, start, cache=0):
        end = min(start+numrecs+1, len(self))
        recs = []
        # XXX This should cache server, db and resultSet
        for r in range(start, end):
            recs.append(self[r].fetch_record(session))
        return recs


try:
    import numarray as na

    class ArrayResultSet(SimpleResultSet):

        _array = None
        recordStore = None
        proxInfo = {}

        def __init__(self, session, data, recordStore = None):
            # data is (docid, freq) array
            self.recordStore = recordStore     
            self.proxInfo = {}
            if len(data) > 0:
                z = na.zeros(len(data), 'f4')[:,na.NewAxis]
                d2 = na.transpose(data)
                z2 = na.transpose(z)
                final = na.transpose(na.concatenate([d2,z2]))
                self._array = final
            else:
                self._array = na.array([])

        def __getitem__(self, k):
            item = SimpleResultSetItem(None, int(self._array[k][0]), self.recordStore.id, int(self._array[k][1]))
            item.weight = self._array[k][2]
            item.proxInfo = self.proxInfo.get(item.id, [])
            return item

        def __len__(self):
            return len(self._array)

        def _toBitmap(self, session):
            bf = SimpleBitfield(0)
            for x in self._array:
                bf[long(x[0])] = 1
            return BitmapResultSet(session, bf)

        # Relevance Rank Algorithms

        def _lrAssign(self, session, others, clause, cql, db):
            if (db):
                totalDocs = db.totalItems
                if totalDocs == 0:
                    raise ValueErorr("No documents in database?")
            else:
                # Uhoh. Can't do it.  (XXX Better Error)
                raise(ValueError("Don't know database for determining relevancy"))

            # William S Cooper proposes:
            constants = [-3.7, 1.269, -0.31, 0.679, -0.0674, 0.223, 2.01]

            # Ray R Larson proposes:
            constants = [-3.7, 1.269, -0.31, 0.679, -0.021, 0.223, 4.01]

            # Index Configuration proposes:
            idx = db.protocolMaps['http://www.loc.gov/zing/srw/'].resolveIndex(session, clause)
            if (idx):
                for x in range(7):
                    temp = idx.get_setting(session, 'lr_constant%d' % x)
                    if (temp):
                        constants[x] = float(temp)

            # Query proposes:
            relSetUri = "info:srw/cql-context-set/2/relevance-1.0"
            for m in cql.modifiers:
                # Already been pinged for resolve()
                if (m.type.prefixURI == relSetUri):
                    if m.type.value[:5] == "const":
                        try:
                            constants[int(m.type.value[5])] = float(m.value)
                        except ValueError:
                            # Invalid literal for float()
                            pass
                        except IndexError:
                            # list index out of range
                            pass

            nors = len(others)
            all = cql.value in ['all', 'and', '=', 'prox', 'adj']
            alst = []

            sumLogQueryFreq = 0.0
            sumQueryFreq = 0
            sumIDF = 0.0

            # Each rs represents one unique word in query
            for rs in others:
                sumLogQueryFreq += math.log(float(rs.queryFreq))
                sumQueryFreq += rs.queryFreq
                if len(rs):
                    n = len(rs)
                    idf = math.log(totalDocs / float(n))
                    # Now stick idf in weight slot for the mean time
                    # Will be replaced with real weight
                    a = rs._array
                    a.transpose()
                    l = [idf] * n
                    b = na.array([l])
                    c = na.concatenate([a,b])
                    c.transpose()
                    alst.append(c)
                    
            x2 = math.sqrt(sumQueryFreq)

            merged = na.concatenate(alst)
            idx = merged.argsort(0)[:,0]
            srtd = na.take(merged, idx)
            lsrtd = len(srtd)

            getSize = self.recordStoreObj.fetch_recordMetadata
            item = None                        
            i = 0
            tmplist = []            
            while i < lsrtd:                
                item = srtd[i]
                n = 1
                sumLogDAF = math.log(item[1])
                sumIdf = item[2]
                i += 1
                if i < lsrtd:
                    nitem = srtd[i]
                    while nitem[0] == item[0]:
                        sumLogDAF += math.log(nitem[1])
                        sumIdf += nitem[2]
                        i += 1
                        n += 1
                        if i < lsrtd:
                            nitem = srtd[i]                            
                        else:
                            break
                if all and n < nors:
                    continue
                x1 = sumLogQueryFreq / float(n)
                x3 = sumLogDAF / float(n)
                x5 = sumIDF / float(n)
                x6 = math.log(float(n))
                doclen = getSize(session, int(item[0]), 'wordCount')
                x4 = math.sqrt(doclen)
                logodds = constants[0] + (constants[1] * x1) + (constants[2] * x2) + \
                          (constants[3] * x3) + (constants[4] * x4) + (constants[5] * x5) + \
                          (constants[6] * x6)
                item[2]= 0.75 * (math.exp(logodds) / (1 + math.exp(logodds)))
                tmplist.append(item)
            return tmplist


        def _coriAssign(self, session, others, clause, cql, db):
            if (db):
                totalDocs = float(db.totalItems)
                avgSize = float(db.meanWordCount)
                if not totalDocs or not avgSize:
                    raise ValueError("0 documents in database")
            else:
                # Uhoh. Can't do it.  (XXX Better Error)
                raise(ValueError("Don't know database for determining relevancy"))

            # CORI proposes:
            constants = [0.5, 50.0, 150.0, 0.4, 0.6]

            # Index Configuration proposes:
            idx = db.protocolMaps['http://www.loc.gov/zing/srw/'].resolveIndex(session, clause)
            if (idx):
                for x in range(7):
                    temp = idx.get_setting(session, 'cori_constant%d' % x)
                    if (temp):
                        constants[x] = float(temp)

            # Query proposes:
            relSetUri = "info:srw/cql-context-set/2/relevance-1.0"
            for m in cql.modifiers:
                # Already been pinged for resolve()
                if (m.type.prefixURI == relSetUri):
                    if m.type.value[:5] == "const":
                        try:
                            constants[int(m.type.value[5])] = float(m.value)
                        except ValueError:
                            # Invalid literal for float() or int()
                            pass
                        except IndexError:
                            # list index out of range
                            pass

            getSize = self.recordStore.fetch_recordMetadata
            for rs in others:
                matches = float(len(rs))
                if not matches:
                    continue
                I = math.log((totalDocs + 0.5) / matches) / math.log(totalDocs + 1.0)
                for i in range(len(rs._array)):
                    item = rs._array[i]
                    # array(id, occs, weight)
                    df = float(item[1])
                    size = getSize(session, int(item[0]), 'wordCount')
                    T = df / ( df + 50.0 + (( 150.0 * size) / avgSize))
                    rs._array[i][2] = 0.4 + (0.6 * T * I)                    
            return []

        def _tfidfAssign(self, session, others, clause, cql, db):
            if (db):
                totalDocs = float(db.totalItems)
                if not totalDocs:
                    raise ValueError("0 documents in database")
            else:
                # Uhoh. Can't do it.  (XXX Better Error)
                raise(ValueError("Don't know database for determining relevancy"))
            for rs in others:
                idf = math.log(totalDocs / float(len(rs)))
                for i in range(len(rs)):
                    rs._array[i][2] = rs._array[i][1] * idf
            return []

        # *** Combine Algorithms ***

        def _meanWeightsArray(self, items, n):
            item = items[0]
            for i in items[1:]:
                item[2] += i[2]
            item[2] = item[2] / float(n)
            return item

        def _sumWeightsArray(self, items, n):
            item = items[0]
            for i in items[1:]:
                item[2] += i[2]
            return item

        # API

        # SLOW
        def combine(self, session, others, clause, db=None):
            if (isinstance(clause, CQLParser.Triple)):
                cql = clause.boolean
            else:
                cql = clause.relation

            # XXX To Configuration
            relSetUri = "info:srw/cql-context-set/2/relevance-1.0"
            cqlSet = "info:srw/cql-context-set/1/cql-v1.1"

            relevancy = 0
            algorithm = "cori"
            combine = "mean"
            modType = ""
            for m in cql.modifiers:
                m.type.parent = clause
                m.type.resolvePrefix()
                if (m.type.prefixURI == relSetUri):
                    # Relevancy info
                    relevancy = 1
                    if m.type.value == "algorithm":
                        algorithm = m.value
                    elif m.type.value == "combine":
                        combine = m.value
                elif (m.type.prefixURI == cqlSet and m.type.value == "relevant"):
                    # Generic 'relevancy please' request
                    relevancy = 1

            # Check if any others are relevance ranked already and preserve
            if (not relevancy):
                for x in others:
                    if (x.relevancy):
                        relevancy = 1
                        break
            pi = 0
            for m in cql.modifiers:
                if m.type.value == 'proxinfo':
                    pi = 1
                    break

            # sort result sets by length
            all = cql.value in ['all', 'and', '=', 'prox', 'adj']                
            if cql.value != "not":
                keys = [(len(x), x) for x in others]
                keys.sort(reverse=not all)
                others = [x for (key,x) in keys]    

            if (relevancy):
                if (isinstance(cql, CQLParser.Relation)):
                    fname = "_%sAssign" % algorithm
                    if (hasattr(self, fname)):
                        fn = getattr(self, fname)
                    else:
                        raise NotImplementedError
                    finish = fn(session, others, clause, cql, db)
                    if finish:
                        return self

            if len(others) == 1:
                # Just adding relevance to items?
                if relevancy:
                    self.relevancy = 1
                return others[0]
            else:
                # Merge                    
                if relevancy:
                    maxWeight = -1
                    minWeight = 9999999999

                tmplist = []
                cont = 1
                oidxs = range(1,len(others))
                lens = [len(x) for x in others]
                nors = len(others)
                positions = [0] * nors
                cmpHash = {'<' : [-1],
                           '<=' : [-1, 0],
                           '=' : [0],
                           '>=' : [0, 1],
                           '>' : [1]}
                distance = 1
                unit = "word"
                comparison = "="
                if (cql.value == 'prox' and cql.modifiers):
                    if (cql['unit']):
                        unit = cql['unit'].value
                    if (cql['distance']):
                        distance = int(cql['distance'].value)
                        comparison = cql['distance'].comparison
                chitem = cmpHash[comparison]
                if unit == "word":
                    proxtype = 1
                elif unit == "element" and distance == 0 and comparison == "=":
                    proxtype = 2
                else:
                    raise NotImplementedError()
                hasGetItemList = [hasattr(o, 'get_item') for o in others]
                isArrayRs = [isinstance(o, ArrayResultSet) for o in others]
                if sum(isArrayRs) == len(isArrayRs):
                    if relevancy:
                        fname = "_%sWeightsArray" % combine
                        if (hasattr(self, fname)):
                            fn = getattr(self, fname)
                        else:
                            raise NotImplementedError

                    # All arrays, don't create RSI unnecessarily
                    while cont:                
                        # item is: array(recid, occs, weight)
                        while others and positions[0] > len(others[0])-1:
                            others.pop(0)
                            positions.pop(0)
                            lens.pop(0)
                        if not others or ((cql.value == 'not' or all) and len(others) != nors):
                            cont = 0
                            break

                        try:
                            items = [others[0]._array[positions[0]]]
                        except IndexError:
                            # Don't know when this would happen?
                            break
                        rspos = [0]
                        for o in oidxs:
                            if o != -1:
                                try:
                                    nitem = others[o]._array[positions[o]]
                                except IndexError:
                                    oidxs[o-1] = -1
                                    continue
                                if nitem[0] < items[0][0]:
                                    if all or cql.value == 'not':
                                        # skip until equal or greater
                                        positions[o] += 1
                                        while others[o]._array[positions[o]][0] < items[0][0]:
                                            positions[o] += 1
                                            if positions[o] == lens[o]:
                                                break
                                        if positions[o] != lens[o]:
                                            nitem = others[o]._array[positions[o]]
                                    else:
                                        items = [nitem]
                                        rspos = [o]
                                        continue
                                if nitem[0] == items[0][0]:
                                    items.append(nitem)
                                    rspos.append(o)
                        for r in rspos:
                            positions[r] += 1

                        if (all and len(items) < nors):
                            continue
                        elif cql.value == 'not' and len(items) != 1:
                            continue
                        elif cql.value in ["prox", 'adj', '=']:

                            if cql.value != 'prox':
                                # only need to check queryPositions for phrase search
                                newitems = []
                                newrspos = []
                                mqp = -1
                                qts = []
                                qps = []
                                for i in range(len(items)):
                                    rs = others[rspos[i]]
                                    qts.append(rs.queryTerm)
                                    qps.append(rs.queryPositions)
                                    for qp in rs.queryPositions:
                                        mqp = max(mqp, qp)
                                for idx in range(mqp+1):
                                    for i in range(len(items)):
                                        if idx in qps[i]:
                                            newitems.append(items[i])
                                            newrspos.append(rspos[i])
                                            break
                                items = newitems[:]
                                rspos = newrspos[:]

                            itemsCopy = items[:]
                            litem = items.pop(0)
                            lProxInfo = others[rspos[0]].proxInfo[litem[0]]
                            nomatch = 0                    
                            oidx = 1

                            while len(items):                        
                                ritem = items.pop(0)
                                rProxInfo = others[rspos[oidx]].proxInfo[ritem[0]]
                                oidx += 1
                                matchlocs = []
                                for (relem, rwpos) in rProxInfo:
                                    for (lelem, lwpos) in lProxInfo:
                                        if (proxtype == 1 and lelem == relem and (cmp(lwpos+distance,rwpos) in chitem)):
                                            matchlocs.append([relem, rwpos])
                                        elif proxtype == 2 and lelem == relem:
                                            matchlocs.append([relem, rwpos])
                                if matchlocs:                                    
                                    lProxInfo = matchlocs
                                    litem = ritem                                
                                else:
                                    # no match, break to next set of items
                                    nomatch = 1
                                    break
                            if nomatch:
                                continue
                            items = itemsCopy
                            self.proxInfo[litem[0]] = matchlocs


                        if relevancy:
                            item = fn(items, nors)
                            if item[2] > maxWeight:
                                maxWeight = item[2]
                            if item[2] < minWeight:
                                minWeight = item[2]
                        else:
                            item = items[0]
                        if pi:
                            # copy proxInfo around
                            raise NotImplementedError
                            for o in items[1:]:
                                item.proxInfo.extend(o.proxInfo)                        
                        tmplist.append(item)

                else:
                    # not all array based, use slower RSI creation

                    if relevancy:
                        fname = "_%sWeights" % combine
                        if (hasattr(self, fname)):
                            fn = getattr(self, fname)
                        else:
                            raise NotImplementedError

                    while cont:                
                        items = [others[0][positions[0]]]
                        rspos = [0]
                        for o in oidxs:
                            if o != -1:
                                if hasGetItemList[o]:
                                    nitem = others[o].get_item(items[0])
                                    if not nitem:
                                        continue
                                else:    
                                    try:
                                        nitem = others[o][positions[o]]
                                    except IndexError:
                                        oidxs[o-1] = -1
                                        continue
                                    if nitem < items[0]:
                                        if all or cql.value == 'not':
                                            # skip until equal or greater
                                            positions[o] += 1
                                            while others[o][positions[o]] < items[0]:
                                                positions[o] += 1
                                                if positions[o] == lens[o]:
                                                    break
                                            if positions[o] != lens[o]:
                                                nitem = others[o][positions[o]]
                                        else:
                                            items = [nitem]
                                            rspos = [o]
                                            continue
                                if nitem == items[0]:
                                    items.append(nitem)
                                    rspos.append(o)

                        for r in rspos:
                            positions[r] += 1

                        while others and positions[0] > len(others[0])-1:
                            others.pop(0)
                            positions.pop(0)
                            lens.pop(0)
                        if not others or ((cql.value == 'not' or all) and len(others) != nors):
                            cont = 0
                        if (all and len(items) < nors):
                            continue
                        elif cql.value == 'not' and len(items) != 1:
                            continue
                        elif cql.value in ["prox", 'adj', '=']:
                            # proxInfo is hash of (docid, recStore) to list of locations in record
                            # sort items by query position. Repeat set at each posn

                            newitems = []
                            mqp = -1
                            for i in items:
                                i.queryTerm = i.resultSet.queryTerm
                                i.queryPositions = i.resultSet.queryPositions
                                for qp in i.queryPositions:
                                    mqp = max(mqp, qp)
                            for idx in range(mqp+1):
                                for i in items:
                                    if idx in i.queryPositions:
                                        newitems.append(i)
                                        break
                            items = newitems[:]
                            litem = items.pop(0)
                            nomatch = 0                    
                            while len(items):                        
                                ritem = items.pop(0)
                                matchlocs = []
                                for r in range(0,len(ritem.proxInfo),2):
                                    relem = ritem.proxInfo[r]
                                    rwpos = ritem.proxInfo[r+1]
                                    for l in range(0, len(litem.proxInfo), 2):
                                        if (proxtype == 1 and litem.proxInfo[l] == relem and (cmp(litem.proxInfo[l+1]+distance,rwpos) in chitem)):
                                            matchlocs.extend([relem, rwpos])
                                        elif proxtype == 2 and litem.proxInfo[l][0] == relem:
                                            matchlocs.extend([relem, rwpos])
                                if matchlocs:                                    
                                    ritem.proxInfo = matchlocs
                                    litem = ritem                                
                                else:
                                    # no match, break to next set of items
                                    nomatch = 1
                                    break
                            if nomatch:
                                continue
                            items = newitems
                        # do stuff on items to reduce to single representative
                        if relevancy:
                            item = fn(items, nors)
                            if item.weight > maxWeight:
                                maxWeight = item.weight
                            if item.weight < minWeight:
                                minWeight = item.weight
                        else:
                            item = items[0]
                        if pi:
                            # copy proxInfo around
                            for o in items[1:]:
                                item.proxInfo.extend(o.proxInfo)                        
                        tmplist.append(na.array([float(item.id), float(item.occurences), item.weight]))

                self._array = na.array(tmplist)
                if relevancy:
                    self.relevancy = 1
                    self.minWeight = minWeight
                    self.maxWeight = maxWeight
                return self


        def order(self, session, spec):
            if (isinstance(spec, Index) and spec.get_setting(session, 'sortStore')):
                # check pre-processed db
                istore = spec.get_path(session, 'indexStore')
                tmplist = [(istore.fetch_sortValue(session, spec, int(x[0])), x) for x in self._array]
                tmplist.sort()
                l = [x for (key,x) in tmplist]
                self._array = na.array(l)
            elif isinstance(spec, Index):
                # Extract data as per indexing, MUCH slower
                tmplist = []
                for r in range(len(self._array)):
                    rec = self.recordStore.fetch_record(session, int(self._array[r][0]))
                    tmplist.append((spec.extract_data(session, rec), r))
                tmplist.sort()
                l = [x for (key,x) in tmplist]
                self._array = self._array.take(na.array(l))
            elif spec == "docid":
                idx = self._array.argsort(0)[::-1,0]
                self._array = self._array.take(idx)
            elif spec == "occurences":
                idx = self._array.argsort(0)[::-1,1]
                self._array = self._array.take(idx)
            elif spec == "relevance":
                idx = self._array.argsort(0)[::-1,2]
                self._array = self._array.take(idx)
            elif isinstance(spec, str):
                tmplist = []
                xp = utils.verifyXPaths([spec])[0]                
                for r in range(len(self._array)):
                    rec = self.recordStore.fetch_record(session, int(self._array[r][0]))
                    tmplist.append((rec.process_xpath(xp), r))
                tmplist.sort()
                l = [x for (key,x) in tmplist]
                self._array = self._array.take(na.array(l))
            else:
                raise NotImplementedError
            
        def reverse(self, session):
            self._array = self._array[::-1]


except:
    raise