"""core/pack_importer.py — Import de packs Shimeji par glisser-déposer ou sélection fichier."""
from __future__ import annotations
import shutil
import zipfile
from pathlib import Path
from typing import Optional


IMG_ROOT = Path("assets/default/img")


def import_pack(source: str | Path) -> tuple[bool, str]:
    """
    Importe un pack Shimeji depuis un ZIP ou un dossier.
    Retourne (succès, message).
    """
    source = Path(source)
    if not source.exists():
        return False, f"Fichier introuvable : {source}"

    if source.suffix.lower() == ".zip":
        return _import_zip(source)
    elif source.is_dir():
        return _import_folder(source)
    else:
        return False, f"Format non supporté : {source.suffix}"


def _import_zip(zip_path: Path) -> tuple[bool, str]:
    """Extrait un ZIP et importe les dossiers de personnages trouvés."""
    imported = []
    errors   = []

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Chercher les dossiers qui contiennent conf/actions.xml
            names = zf.namelist()
            char_roots = _find_char_roots_in_zip(names, zip_path.stem)

            if not char_roots:
                return False, (
                    "Aucun personnage Shimeji trouvé dans ce ZIP.\n"
                    "Vérifier que le ZIP contient un dossier avec conf/actions.xml"
                )

            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                zf.extractall(tmp)
                tmp_path = Path(tmp)

                for char_root in char_roots:
                    char_dir = tmp_path / char_root
                    if not char_dir.exists():
                        # ZIP plat : contenu extrait à la racine de tmp_path
                        char_dir.mkdir()
                        for item in list(tmp_path.iterdir()):
                            if item.name != char_root:
                                item.rename(char_dir / item.name)
                    ok, msg  = _copy_char_dir(char_dir)
                    if ok:
                        imported.append(msg)
                    else:
                        errors.append(msg)

    except zipfile.BadZipFile:
        return False, "Fichier ZIP corrompu ou invalide."
    except Exception as e:
        return False, f"Erreur lors de l'extraction : {e}"

    if imported:
        msg = f"✓ {len(imported)} personnage(s) importé(s) : {', '.join(imported)}"
        if errors:
            msg += f"\n⚠ {len(errors)} erreur(s) : {', '.join(errors)}"
        return True, msg
    return False, f"Aucun personnage importé. Erreurs : {', '.join(errors)}"


def _import_folder(folder: Path) -> tuple[bool, str]:
    """Importe directement un dossier de personnage."""
    ok, msg = _copy_char_dir(folder)
    return ok, msg


def _find_char_roots_in_zip(names: list[str], zip_stem: str = "Character") -> list[str]:
    """Trouve les racines de personnages dans un ZIP (dossiers contenant conf/actions.xml)."""
    roots = set()
    for name in names:
        p = Path(name)
        # Chercher conf/actions.xml
        if p.parts and p.name == "actions.xml":
            parts = p.parts
            # conf/actions.xml → racine = dossier parent de conf/
            for i, part in enumerate(parts):
                if part == "conf":
                    if i > 0:
                        root = str(Path(*parts[:i]))
                    else:
                        root = zip_stem
                    roots.add(root)
                    break
    return sorted(roots)


def _copy_char_dir(source: Path) -> tuple[bool, str]:
    """Copie un dossier de personnage dans assets/default/img/."""
    if not source.is_dir():
        return False, f"Pas un dossier : {source.name}"

    # Vérifier conf/actions.xml
    if not (source / "conf" / "actions.xml").exists():
        return False, f"Pas de conf/actions.xml dans {source.name}"

    # Vérifier PNG
    pngs = list(source.glob("*.png")) + list(source.glob("*.PNG"))
    if not pngs:
        return False, f"Pas de sprites PNG dans {source.name}"

    char_name = source.name
    dest      = IMG_ROOT / char_name

    if dest.exists():
        # Sauvegarder l'ancien et remplacer
        backup = IMG_ROOT / f"{char_name}_backup"
        if backup.exists():
            shutil.rmtree(backup)
        shutil.copytree(dest, backup)
        shutil.rmtree(dest)

    try:
        shutil.copytree(source, dest)
        return True, char_name
    except Exception as e:
        return False, f"{char_name}: {e}"


def scan_available_chars() -> list[Path]:
    """Rescanne les personnages disponibles après un import."""
    if not IMG_ROOT.exists():
        return []
    return sorted([
        d for d in IMG_ROOT.iterdir()
        if d.is_dir()
        and (d / "conf" / "actions.xml").exists()
        and (any(d.glob("*.png")) or any(d.glob("*.PNG")))
    ])
