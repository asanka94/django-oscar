from elasticsearch_dsl import TermsFacet


class AutoRangeFacet(TermsFacet):
    """
    Custom facet class used for our `auto_range` facet type. The results returned are the same as those for a TermsFacet
    agg but processed and displayed like a range facet.
    """
    pass
