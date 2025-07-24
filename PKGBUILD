#Maintainer: Avery Visentin <averyvisentin@gmail.com>

pypiname=terminal_tetris
pkgname=python-terminal-tetris
pkgver=0.0.10
pkgrel=1
pkgdesc="A simple Tetris game for the terminal."
arch=('any')
url="https://github.com/averyvisentin/terminal-tetris"
license=('MIT')

depends=('python-blessed')
makedepends=('python-installer') # Only installer is needed now

# Use the pre-built wheel from the dist folder
source=("$pypiname-$pkgver-py3-none-any.whl::https://files.pythonhosted.org/packages/source/t/$pypiname/$pypiname-$pkgver.tar.gz") # This URL will need to point to your actual .whl file

sha256sums=('cc0fe8f333b5e5aa8d67ca6a99e9ad8c3e9db6786e4c704da12d3d9a6551c708')

# The package() function installs the built files into the staging directory '$pkgdir'.
package() {
  # Use the standard PEP 517 installer tool, 'python-installer'.
  # --destdir="$pkgdir": This is the modern, correct replacement for the old '--root'
  # hack. It directs the installation into the package staging directory.
  python -m installer --destdir="$pkgdir" "$srcdir/$pypiname-$pkgver-py3-none-any.whl"

  # The license should be installed under the Arch package name
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
