# http://code.activestate.com/recipes/303060-group-a-list-into-sequential-n-tuples/
def group(lst, n):
    """group a list into consecutive n-tuples
    
    >>> group(range(10), 3)
    [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    
    >>> group([0, 3, 4, 10, 2, 3], 2)
    [(0, 3), (4, 10), (2, 3)]
    """
    if (len(lst) % n != 0):
        raise ValueError(f"Provided list of length {len(lst)} is not "
            f"divisible by {n}")
    return zip(*[lst[i::n] for i in range(n)]) 

def get_person_from_match(user_id, match):
    """given a Match, return the Person corresponding to the passed user ID
    """
    if match.person_1.user_id == user_id:
        return match.person_1
    elif match.person_2.user_id == user_id:
        return match.person_2
    else:
        raise Exception(f"Person with user ID \"{user_id}\" is not part of "
            f"the passed match ({match}).")

def get_other_person_from_match(user_id, match):
    """given a Match, return the Person corresponding to the user who is NOT
    the passed user ID (i.e. the other Person)
    """
    if match.person_1.user_id == user_id:
        return match.person_2
    elif match.person_2.user_id == user_id:
        return match.person_1
    else:
        raise Exception(f"Person with user ID \"{user_id}\" is not part of "
            f"the passed match ({match}).")
