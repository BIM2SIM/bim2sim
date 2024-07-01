"""Example file for doc strings,"""

# Sphinx param and type parts of the docstring:
def function_foo_sphinx(x, y, z):
    '''function foo ...

    :param x: bla x
    :type x: int

    :param y: bla y
    :type y: float

    :param int z: bla z

    :return: sum
    :rtype: float
    '''
    return x + y + z

# or the Google style Args: part of the docstring:

def function_foo_google(x, y, z):
    '''function foo ...

    Args:
        x (int): bla x
        y (float): bla y

        z (int): bla z

    Returns:
        float: sum
    '''
    return x + y + z

# or the Numpy style Parameters part of the docstring:

def function_foo_numpy(x, y, z):
    '''function foo ...

    Parameters
    ----------
    x: int
        bla x
    y: float
        bla y

    z: int
        bla z

    Returns
    -------
    float
        sum
    '''
    return x + y + z
