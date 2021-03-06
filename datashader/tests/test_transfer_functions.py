from __future__ import division

from io import BytesIO

import numpy as np
import xarray as xr
import PIL
import pytest

import datashader.transfer_functions as tf


coords = [np.array([0, 1, 2]), np.array([3, 4, 5])]
dims = ['y_axis', 'x_axis']

a = np.arange(10, 19, dtype='i4').reshape((3, 3))
a[[0, 1, 2], [0, 1, 2]] = 0
s_a = xr.DataArray(a, coords=coords, dims=dims)
b = np.arange(10, 19, dtype='f4').reshape((3, 3))
b[[0, 1, 2], [0, 1, 2]] = np.nan
s_b = xr.DataArray(b, coords=coords, dims=dims)
c = np.arange(10, 19, dtype='f8').reshape((3, 3))
c[[0, 1, 2], [0, 1, 2]] = np.nan
s_c = xr.DataArray(c, coords=coords, dims=dims)
agg = xr.Dataset(dict(a=s_a, b=s_b, c=s_c))

int_span = [11, 17]
float_span = [11.0, 17.0]

solution_lists = {
    'log':
        [[0, 4291543295, 4286741503],
         [4283978751, 0, 4280492543],
         [4279242751, 4278190335, 0]],
    'cbrt':
        [[0, 4291543295, 4284176127],
         [4282268415, 0, 4279834879],
         [4278914047, 4278190335, 0]],
    'linear':
        [[0, 4291543295, 4289306879],
         [4287070463, 0, 4282597631],
         [4280361215, 4278190335, 0]]
}

solutions = {how: xr.DataArray(np.array(v, dtype='u4'),
                               coords=coords, dims=dims)
             for how, v in solution_lists.items()}

eq_hist_sol = {'a': np.array([[0, 4291543295, 4288846335],
                              [4286149631, 0, 4283518207],
                              [4280821503, 4278190335, 0]], dtype='u4'),
               'b': np.array([[0, 4291543295, 4288846335],
                              [4286609919, 0, 4283518207],
                              [4281281791, 4278190335, 0]], dtype='u4')}
eq_hist_sol['c'] = eq_hist_sol['b']


def check_span(x, cmap, how, sol):
    # Copy inputs that will be modified
    sol = sol.copy()
    x = x.copy()

    # All data no span
    img = tf.shade(x, cmap=cmap, how=how, span=None)
    assert img.equals(sol)

    # All data with span
    img = tf.shade(x, cmap=cmap, how=how, span=float_span)
    assert img.equals(sol)

    # Decrease smallest. This value should be clipped to span[0] and the
    # resulting image should be identical
    x[0, 1] = 10
    x_input = x.copy()
    img = tf.shade(x, cmap=cmap, how=how, span=float_span)
    assert img.equals(sol)

    # Check that clipping doesn't alter input array
    assert x.equals(x_input)

    # Increase largest. This value should be clipped to span[1] and the
    # resulting image should be identical
    x[2, 1] = 18
    x_input = x.copy()
    img = tf.shade(x, cmap=cmap, how=how, span=float_span)
    assert img.equals(sol)

    # Check that clipping doesn't alter input array
    assert x.equals(x_input)

    # zero out smallest. If span is working properly the zeroed out pixel
    # will be masked out and all other pixels will remain unchanged
    x[0, 1] = 0 if x.dtype.kind == 'i' else np.nan
    img = tf.shade(x, cmap=cmap, how=how, span=float_span)
    sol[0, 1] = sol[0, 0]
    assert img.equals(sol)

    # zero out the largest value
    x[2, 1] = 0 if x.dtype.kind == 'i' else np.nan
    img = tf.shade(x, cmap=cmap, how=how, span=float_span)
    sol[2, 1] = sol[0, 0]
    assert img.equals(sol)


@pytest.mark.parametrize('attr', ['a', 'b', 'c'])
@pytest.mark.parametrize('span', [None, int_span, float_span])
def test_shade(attr, span):
    x = getattr(agg, attr)
    cmap = ['pink', 'red']

    img = tf.shade(x, cmap=cmap, how='log', span=span)
    sol = solutions['log']
    assert img.equals(sol)

    img = tf.shade(x, cmap=cmap, how='cbrt', span=span)
    sol = solutions['cbrt']
    assert img.equals(sol)

    img = tf.shade(x, cmap=cmap, how='linear', span=span)
    sol = solutions['linear']
    assert img.equals(sol)

    # span option not supported with how='eq_hist'
    img = tf.shade(x, cmap=cmap, how='eq_hist')
    sol = xr.DataArray(eq_hist_sol[attr], coords=coords, dims=dims)
    assert img.equals(sol)

    img = tf.shade(x, cmap=cmap,
                   how=lambda x, mask: np.where(mask, np.nan, x ** 2))
    sol = np.array([[0, 4291543295, 4291148543],
                    [4290030335, 0, 4285557503],
                    [4282268415, 4278190335, 0]], dtype='u4')
    sol = xr.DataArray(sol, coords=coords, dims=dims)
    assert img.equals(sol)


@pytest.mark.parametrize('attr', ['a', 'b', 'c'])
@pytest.mark.parametrize('how', ['linear', 'log', 'cbrt'])
def test_span_cmap_list(attr, how):
    # Get input
    x = getattr(agg, attr).copy()

    # Build colormap
    cmap = ['pink', 'red']

    # Get expected solution for interpolation method
    sol = solutions[how]

    # Check span
    check_span(x, cmap, how, sol)


@pytest.mark.parametrize('cmap', ['black', (0, 0, 0), '#000000'])
def test_span_cmap_single(cmap):
    # Get input
    x = agg.a

    # Build expected solution DataArray
    sol = np.array([[0, 671088640, 1946157056],
                    [2701131776, 0, 3640655872],
                    [3976200192, 4278190080, 0]])
    sol = xr.DataArray(sol, coords=coords, dims=dims)

    # Check span
    check_span(x, cmap, 'log', sol)


def test_span_cmap_mpl():
    # Get inputs
    x = agg.a

    # Get MPL colormap
    cm = pytest.importorskip('matplotlib.cm')
    cmap = cm.viridis

    # Build expected solution Data Array
    sol = np.array([[5505348, 4283695428, 4287524142],
                    [4287143710, 5505348, 4282832267],
                    [4280213706, 4280608765, 5505348]])
    sol = xr.DataArray(sol, coords=coords, dims=dims)

    # Check span
    check_span(x, cmap, 'log', sol)


def test_shade_bool():
    data = ~np.eye(3, dtype='bool')
    x = xr.DataArray(data, coords=coords, dims=dims)
    sol = xr.DataArray(np.where(data, 4278190335, 0).astype('uint32'),
                       coords=coords, dims=dims)
    img = tf.shade(x, cmap=['pink', 'red'], how='log')
    assert img.equals(sol)
    img = tf.shade(x, cmap=['pink', 'red'], how='cbrt')
    assert img.equals(sol)
    img = tf.shade(x, cmap=['pink', 'red'], how='linear')
    assert img.equals(sol)
    img = tf.shade(x, cmap=['pink', 'red'], how='eq_hist')
    assert img.equals(sol)


def test_shade_cmap():
    cmap = ['red', (0, 255, 0), '#0000FF']
    img = tf.shade(agg.a, how='log', cmap=cmap)
    sol = np.array([[0, 4278190335, 4278236489],
                    [4280344064, 0, 4289091584],
                    [4292225024, 4294901760, 0]])
    sol = xr.DataArray(sol, coords=coords, dims=dims)
    assert img.equals(sol)


@pytest.mark.parametrize('cmap', ['black', (0, 0, 0), '#000000'])
def test_shade_cmap_non_categorical_alpha(cmap):
    img = tf.shade(agg.a, how='log', cmap=cmap)
    sol = np.array([[         0,  671088640, 1946157056],
                    [2701131776,          0, 3640655872],
                    [3976200192, 4278190080,          0]])
    sol = xr.DataArray(sol, coords=coords, dims=dims)
    assert img.equals(sol)


def test_shade_cmap_errors():
    with pytest.raises(ValueError):
        tf.shade(agg.a, cmap='foo')

    with pytest.raises(ValueError):
        tf.shade(agg.a, cmap=[])


def test_shade_mpl_cmap():
    cm = pytest.importorskip('matplotlib.cm')
    img = tf.shade(agg.a, how='log', cmap=cm.viridis)
    sol = np.array([[5505348, 4283695428, 4287524142],
                    [4287143710, 5505348, 4282832267],
                    [4280213706, 4280608765, 5505348]])
    sol = xr.DataArray(sol, coords=coords, dims=dims)
    assert img.equals(sol)


def test_shade_category():
    coords = [np.array([0, 1]), np.array([2, 5])]
    cat_agg = xr.DataArray(np.array([[(0, 12, 0), (3, 0, 3)],
                                    [(12, 12, 12), (24, 0, 0)]]),
                           coords=(coords + [['a', 'b', 'c']]),
                           dims=(dims + ['cats']))

    colors = [(255, 0, 0), '#0000FF', 'orange']

    img = tf.shade(cat_agg, color_key=colors, how='log', min_alpha=20)
    sol = np.array([[2583625728, 335565567],
                    [4283774890, 3707764991]], dtype='u4')
    sol = tf.Image(sol, coords=coords, dims=dims)
    assert img.equals(sol)

    colors = dict(zip('abc', colors))

    img = tf.shade(cat_agg, color_key=colors, how='cbrt', min_alpha=20)
    sol = np.array([[2650734592, 335565567],
                    [4283774890, 3657433343]], dtype='u4')
    sol = tf.Image(sol, coords=coords, dims=dims)
    assert img.equals(sol)

    img = tf.shade(cat_agg, color_key=colors, how='linear', min_alpha=20)
    sol = np.array([[1140785152, 335565567],
                    [4283774890, 2701132031]], dtype='u4')
    sol = tf.Image(sol, coords=coords, dims=dims)
    assert img.equals(sol)

    img = tf.shade(cat_agg, color_key=colors,
                   how=lambda x, m: np.where(m, np.nan, x) ** 2,
                   min_alpha=20)
    sol = np.array([[503250944, 335565567],
                    [4283774890, 1744830719]], dtype='u4')
    sol = tf.Image(sol, coords=coords, dims=dims)
    assert img.equals(sol)


coords2 = [np.array([0, 2]), np.array([3, 5])]
img1 = tf.Image(np.array([[0xff00ffff, 0x00000000],
                          [0x00000000, 0xff00ff7d]], dtype='uint32'),
                coords=coords2, dims=dims)
img2 = tf.Image(np.array([[0x00000000, 0x00000000],
                          [0x000000ff, 0x7d7d7dff]], dtype='uint32'),
                coords=coords2, dims=dims)


def test_set_background():
    out = tf.set_background(img1)
    assert out.equals(img1)
    sol = tf.Image(np.array([[0xff00ffff, 0xff0000ff],
                             [0xff0000ff, 0xff00ff7d]], dtype='uint32'),
                   coords=coords2, dims=dims)
    out = tf.set_background(img1, 'red')
    assert out.equals(sol)


def test_stack():
    img = tf.stack(img1, img2)
    out = np.array([[0xff00ffff, 0x00000000],
                    [0x00000000, 0xff3dbfbc]], dtype='uint32')
    assert (img.x_axis == img1.x_axis).all()
    assert (img.y_axis == img1.y_axis).all()
    np.testing.assert_equal(img.data, out)

    img = tf.stack(img2, img1)
    out = np.array([[0xff00ffff, 0x00000000],
                    [0x00000000, 0xff00ff7d]], dtype='uint32')
    assert (img.x_axis == img1.x_axis).all()
    assert (img.y_axis == img1.y_axis).all()
    np.testing.assert_equal(img.data, out)

    img = tf.stack(img1, img2, how='add')
    out = np.array([[0xff00ffff, 0x00000000],
                    [0x00000000, 0xff3d3cfa]], dtype='uint32')
    assert (img.x_axis == img1.x_axis).all()
    assert (img.y_axis == img1.y_axis).all()
    np.testing.assert_equal(img.data, out)


def test_masks():
    # Square
    mask = tf._square_mask(2)
    np.testing.assert_equal(mask, np.ones((5, 5), dtype='bool'))
    np.testing.assert_equal(tf._square_mask(0), np.ones((1, 1), dtype='bool'))
    # Circle
    np.testing.assert_equal(tf._circle_mask(0), np.ones((1, 1), dtype='bool'))
    out = np.array([[1, 1, 1],
                    [1, 1, 1],
                    [1, 1, 1]], dtype='bool')
    np.testing.assert_equal(tf._circle_mask(1), out)
    out = np.array([[0, 0, 1, 1, 1, 0, 0],
                    [0, 1, 1, 1, 1, 1, 0],
                    [1, 1, 1, 1, 1, 1, 1],
                    [1, 1, 1, 1, 1, 1, 1],
                    [1, 1, 1, 1, 1, 1, 1],
                    [0, 1, 1, 1, 1, 1, 0],
                    [0, 0, 1, 1, 1, 0, 0]], dtype='bool')
    np.testing.assert_equal(tf._circle_mask(3), out)


def test_spread():
    p = 0x7d00007d
    g = 0x7d00FF00
    b = 0x7dFF0000
    data = np.array([[p, p, 0, 0, 0],
                     [p, g, 0, 0, 0],
                     [0, 0, 0, 0, 0],
                     [0, 0, 0, b, 0],
                     [0, 0, 0, 0, 0]], dtype='uint32')
    coords = [np.arange(5), np.arange(5)]
    img = tf.Image(data, coords=coords, dims=dims)

    s = tf.spread(img)
    o = np.array([[0xed00863b, 0xed00863b, 0xbc00a82a, 0x00000000, 0x00000000],
                  [0xed00863b, 0xed00863b, 0xbc00a82a, 0x00000000, 0x00000000],
                  [0xbc00a82a, 0xbc00a82a, 0xbca85600, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000]])
    np.testing.assert_equal(s.data, o)
    assert (s.x_axis == img.x_axis).all()
    assert (s.y_axis == img.y_axis).all()
    assert s.dims == img.dims

    s = tf.spread(img, px=2)
    o = np.array([[0xed00863b, 0xed00863b, 0xed00863b, 0xbc00a82a, 0x00000000],
                  [0xed00863b, 0xed00863b, 0xf581411c, 0xdc904812, 0x7dff0000],
                  [0xed00863b, 0xf581411c, 0xed864419, 0xbca85600, 0x7dff0000],
                  [0xbc00a82a, 0xdc904812, 0xbca85600, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000, 0x7dff0000]])
    np.testing.assert_equal(s.data, o)

    s = tf.spread(img, shape='square')
    o = np.array([[0xed00863b, 0xed00863b, 0xbc00a82a, 0x00000000, 0x00000000],
                  [0xed00863b, 0xed00863b, 0xbc00a82a, 0x00000000, 0x00000000],
                  [0xbc00a82a, 0xbc00a82a, 0xbca85600, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000]])
    np.testing.assert_equal(s.data, o)

    s = tf.spread(img, how='add')
    o = np.array([[0xff007db7, 0xff007db7, 0xfa007f3e, 0x00000000, 0x00000000],
                  [0xff007db7, 0xff007db7, 0xfa007f3e, 0x00000000, 0x00000000],
                  [0xfa007f3e, 0xfa007f3e, 0xfa7f7f00, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x7dff0000, 0x7dff0000]])
    np.testing.assert_equal(s.data, o)

    mask = np.array([[1, 0, 1],
                     [0, 1, 0],
                     [1, 0, 1]])
    s = tf.spread(img, mask=mask)
    o = np.array([[0xbc00a82a, 0xbc00007d, 0x7d00ff00, 0x00000000, 0x00000000],
                  [0xbc00007d, 0xbc00a82a, 0x7d00007d, 0x00000000, 0x00000000],
                  [0x7d00ff00, 0x7d00007d, 0xbca85600, 0x00000000, 0x7dff0000],
                  [0x00000000, 0x00000000, 0x00000000, 0x7dff0000, 0x00000000],
                  [0x00000000, 0x00000000, 0x7dff0000, 0x00000000, 0x7dff0000]])
    np.testing.assert_equal(s.data, o)

    s = tf.spread(img, px=0)
    np.testing.assert_equal(s.data, img.data)

    pytest.raises(ValueError, lambda: tf.spread(img, px=-1))
    pytest.raises(ValueError, lambda: tf.spread(img, mask=np.ones(2)))
    pytest.raises(ValueError, lambda: tf.spread(img, mask=np.ones((2, 2))))


def test_density():
    b = 0xffff0000
    data = np.full((4, 4), b, dtype='uint32')
    assert tf._density(data) == 1.0
    data = np.zeros((4, 4), dtype='uint32')
    assert tf._density(data) == np.inf
    data[2, 2] = b
    assert tf._density(data) == 0
    data[2, 1] = data[1, 2] = data[1, 1] = b
    assert np.allclose(tf._density(data), 3./8.)


def test_dynspread():
    b = 0xffff0000
    data = np.array([[b, b, 0, 0, 0],
                     [b, b, 0, 0, 0],
                     [0, 0, 0, 0, 0],
                     [0, 0, 0, b, 0],
                     [0, 0, 0, 0, 0]], dtype='uint32')
    coords = [np.arange(5), np.arange(5)]
    img = tf.Image(data, coords=coords, dims=dims)
    assert tf.dynspread(img).equals(tf.spread(img, 1))
    assert tf.dynspread(img, threshold=0.9).equals(tf.spread(img, 2))
    assert tf.dynspread(img, threshold=0).equals(img)
    assert tf.dynspread(img, max_px=0).equals(img)

    pytest.raises(ValueError, lambda: tf.dynspread(img, threshold=1.1))
    pytest.raises(ValueError, lambda: tf.dynspread(img, max_px=-1))


def check_eq_hist_cdf_slope(eq):
    # Check that the slope of the cdf is ~1
    # Adapted from scikit-image's test for the same function
    cdf = np.histogram(eq[~np.isnan(eq)], bins=256)[0].cumsum()
    cdf = cdf / cdf[-1]
    slope = np.polyfit(np.linspace(0, 1, cdf.size), cdf, 1)[0]
    assert 0.9 < slope < 1.1


def test_eq_hist():
    # Float
    data = np.random.normal(size=300**2)
    data[np.random.randint(300**2, size=100)] = np.nan
    data = (data - np.nanmin(data)).reshape((300, 300))
    mask = np.isnan(data)
    eq = tf.eq_hist(data, mask)
    check_eq_hist_cdf_slope(eq)
    assert (np.isnan(eq) == mask).all()
    # Integer
    data = np.random.normal(scale=100, size=(300, 300)).astype('i8')
    data = data - data.min()
    eq = tf.eq_hist(data)
    check_eq_hist_cdf_slope(eq)


def test_Image_to_pil():
    img = img1.to_pil()
    assert isinstance(img, PIL.Image.Image)


def test_Image_to_bytesio():
    bytes = img1.to_bytesio()
    assert isinstance(bytes, BytesIO)
    assert bytes.tell() == 0


def test_shade_should_handle_zeros_array():
    data = np.array([[0, 0, 0, 0, 0],
                     [0, 0, 0, 0, 0],
                     [0, 0, 0, 0, 0],
                     [0, 0, 0, 0, 0],
                     [0, 0, 0, 0, 0]], dtype='uint32')
    arr = xr.DataArray(data, dims=['x', 'y'])
    img = tf.shade(arr, cmap=['white', 'black'], how='linear')
    assert img is not None
