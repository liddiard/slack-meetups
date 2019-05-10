# http://code.activestate.com/recipes/303060-group-a-list-into-sequential-n-tuples/
def group(lst, n):
    """
    Group a list into consecutive n-tuples. Incomplete tuples are
    discarded e.g.
    
    >>> group(range(10), 3)
    [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    
    >>> group([0, 3, 4, 10, 2, 3], 2)
    [(0, 3), (4, 10), (2, 3)]
    """
    return zip(*[lst[i::n] for i in range(n)]) 
