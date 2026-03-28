from unittest.mock import patch
import pytest

from src.importrr.exifhelper import adjust_extensions

@patch('src.importrr.exifhelper.run_exiftool')
def test_adjust_extensions_params(mock_run_exiftool):
    import_dir = '/test/import/dir'
    root_dir = '/test/root/dir'

    adjust_extensions(import_dir, root_dir)

    expected_params = [
        '-filename<%f.$fileTypeExtension',
        '-ext', 'GIF',
        '-ext', 'JPG',
        '-ext', 'PNG',
        '-ext', '3GP',
        '-ext', 'MOV',
        '-ext', 'MP4',
        import_dir
    ]

    mock_run_exiftool.assert_called_once_with(root_dir, expected_params)


@patch('src.importrr.exifhelper.run_exiftool')
@pytest.mark.parametrize("tag", ["CreationDate", "CreateDate"])
def test_backfill_video_tag_params(mock_run_exiftool, tag):
    import_dir = '/test/import/dir'
    root_dir = '/test/root/dir'

    from src.importrr.exifhelper import backfill_video_tag
    backfill_video_tag(import_dir, root_dir, tag)

    expected_params = [
        '-overwrite_original',
        '-datetimeoriginal<' + tag,
        '-time:all<$' + tag,
        '-if',
        'not $datetimeoriginal',
        '-ext', '3GP',
        '-ext', 'MOV',
        '-ext', 'MP4',
        import_dir
    ]

    mock_run_exiftool.assert_called_once_with(root_dir, expected_params)
