# Maintainer: (unset — this is a personal-scale project, docs/ROADMAP.md M6)
#
# Builds directly from this repo checkout (no source= download) — the
# supported flow today is `makepkg -si` run from inside a clone, the
# same "full source checkout already present" assumption
# docs/DESIGN.md §14 makes for install-service too. A source=()
# tarball pointing at a tagged GitHub release is real follow-up work
# for an actual AUR submission (docs/ROADMAP.md M6), not done here.
#
# python-secretspec has no known Arch/AUR package as of this writing —
# depends= below is honest about that gap rather than inventing a
# package name that doesn't exist; `uv build`'s isolated build
# environment resolves it from PyPI regardless, same as `uv sync`
# does for development.

pkgname=spork
pkgver=0.1.0
pkgrel=1
pkgdesc="Tiered, JMAP-native email triage daemon + CLI for a single Fastmail account"
arch=('any')
url="https://github.com/stainless5166/friendly-octo-spork"
license=('MIT')
depends=('python' 'python-pydantic' 'python-typer')  # python-secretspec: see note above
makedepends=('uv' 'python-installer')
source=()
sha256sums=()

build() {
  cd "$startdir"
  uv build --wheel --out-dir "$srcdir/dist"
}

package() {
  cd "$startdir"
  python -m installer --destdir="$pkgdir" "$srcdir"/dist/*.whl

  # The same tracked unit template `spork install-service` embeds a copy
  # of (spork.core.systemd.template.UNIT_FILE_CONTENT) — one
  # definition, two install paths. The vendor unit dir
  # (/usr/lib/systemd/user/), not ~/.config/systemd/user/: a
  # distro-managed unit belongs in the package tree, never a user's
  # own config directory (docs/DESIGN.md §14).
  install -Dm644 systemd/sporkd@.service \
    "$pkgdir/usr/lib/systemd/user/sporkd@.service"

  install -Dm644 secretspec.toml \
    "$pkgdir/usr/share/doc/$pkgname/secretspec.toml"
  install -Dm644 README.md \
    "$pkgdir/usr/share/doc/$pkgname/README.md"
  install -Dm644 LICENSE \
    "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
