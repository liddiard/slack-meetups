import re


# regex for a user or channel mention at the beginning of a message
# example matches: " <@UJQ07L30Q> ", "<#C010P8N1ABB|interns>"
# interactive playground: https://regex101.com/r/2Z7eun/2
MENTION_PATTERN = r"(?:^\s?<@(.*?)>\s?)|(?:^\s?<#(.*?)\|.*?>\s?)"


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


def blockquote(message):
    """return `message` with markdown blockquote formatting (start each line
    with "> ")
    """
    if message:
        return re.sub(r"^", "> ", message, flags=re.MULTILINE)
    else:
        return None


def get_mention(message):
    """get the user or channel ID mentioned at the beginning of a message, if
    any
    """
    match = re.search(MENTION_PATTERN, message)
    if match:
        # return the first not-None value in the match group tuple, be it a
        # user or channel mention
        # https://stackoverflow.com/a/18533669
        return next(group for group in match.group(1, 2) if group is not None)
    else:
        return None


def remove_mention(message):
    """remove the user or channel mention from the beginning of a message, if
    any
    """
    return re.sub(MENTION_PATTERN, "", message, count=1)
