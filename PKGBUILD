# Maintainer: Your Name <averyvisentin@gmail.com>
pkgname=terminal_tetris
pkgver=0.0.3  # Replace with your project's current version
pkgrel=1
pkgdesc="A simple Tetris game for the terminal." # A short description
arch=('any') # 'any' is for pure Python projects
url="https://github.com/averyvisentin/terminal-tetris" # Link to your project's homepage/repo
license=('MIT') # Use the SPDX identifier for your project's license

# Arch Linux dependencies.
# List python libraries your project needs.
# Check the Arch repos for package names (e.g., 'requests' on PyPI is 'python-requests' on Arch).
depends=('python-blessed')
# If your project needed 'pygame', you would add 'python-pygame' here.

# Dependencies needed only for building the package.
makedepends=('python-setuptools' 'python-wheel' 'python-build')

# This tells makepkg where to get the source code from.
# The URL format for PyPI source is standard.
source=("$pkgname-$pkgver.tar.gz::https://files.pythonhosted.org/packages/source/t/$pkgname/$pkgname-$pkgver.tar.gz")

# This is a checksum to verify the integrity of the downloaded source.
# We will generate this automatically in the next step.
sha256sums=('cfc1db073db5fbc8bcb9c87d43f57977366e88b98e7492ca477d6872d4b6d72e')

# This function builds the source code. For most Python projects, it's not needed.
# build() {
#   cd "$pkgname-$pkgver"
#   python setup.py build
# }

# This function installs the package into a temporary directory ($pkgdir).
package() {
  cd "$pkgname-$pkgver"
  python -m build --wheel --no-isolation
  pip install --root="$pkgdir" --no-deps --no-user dist/*.whl

  # Install license file
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
