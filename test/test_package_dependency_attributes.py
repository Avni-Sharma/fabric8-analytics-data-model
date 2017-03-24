from entities.package import Package
from entities.version import Version
from data_importer import import_from_folder
import logging
import config

logging.basicConfig(filename=config.LOGFILE_PATH, level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_create_package_entity():

    packages = Package.find_all()
    assert (len(packages) == 0)

    import_from_folder('test/data/S3-maven/maven--org.slf4j:slf4j-api')

    criteria_dict = {'ecosystem': 'maven', 'name': 'org.slf4j:slf4j-api'}
    p = Package.find_by_criteria('Package', criteria_dict)
    assert p.latest_version == '1.7.22'

    p.save()  # must be an update
    assert (Package.count() == 2)

    p.create()  # duplicate should not create new node
    assert (Package.count() == 2)

    criteria_dict = {'ecosystem': 'maven', 'name': 'junit:junit'}
    p2 = Package.find_by_criteria('Package', criteria_dict)

    assert p2.latest_version == ''

    import_from_folder('test/data/S3-maven/maven--junit:junit')

    criteria_dict = {'ecosystem': 'maven', 'name': 'junit:junit'}
    p3 = Package.find_by_criteria('Package', criteria_dict)
    assert p3.latest_version == '4.12'

    p.save()  # must be an update
    assert (Package.count() == 2)

    Package.delete_all()
    assert (Package.count() == 0)

    Version.delete_all()
    assert (Version.count() == 0)

