from graph_populator import GraphPopulator
from entities.utils import get_values as gv
import logging
import sys
import config
import traceback
import json
import os
import requests
from optparse import OptionParser
from datetime import datetime
import set_logging 

from data_source.local_filesystem_data_source import LocalFileSystem
from data_source.s3_data_source import S3DataSource
from data_source.rds_book_keeper import RDSBookKeeper

logger = logging.getLogger(__name__)


def _group_keys_s3(all_keys):
    grouped_keys = {}
    counter = 0
    for key in all_keys:
        if len(key.split("/")) == 3:
            counter += 1
            grouped_keys[counter] = []
        if key.endswith("json"):
            grouped_keys[counter].append(key)

    return grouped_keys


def _group_keys_directory(all_keys, packages_path):
    grouped_keys = {}
    counter = 0
    grouped_keys[counter] = []
    version_json = json.load(open(os.path.join(packages_path, all_keys[0])))
    version = version_json["version"]
    for key in all_keys:
        if version not in key:
            counter += 1
            version_json = json.load(open(os.path.join(packages_path, key)))
            version = version_json["version"]
            grouped_keys[counter] = []
        if key.endswith("json"):
            grouped_keys[counter].append(key)    
    return grouped_keys


def _group_keys_by_epv(all_keys, data_source):
    if data_source.get_source_name() == "S3":
        return _group_keys_s3(all_keys)
    else:
        return _group_keys_directory(all_keys, data_source.src_dir)


def _first_key_info(data_source, first_key, bucket_name=None):
    obj = {}
    t = data_source.read_json_file(first_key, bucket_name)
    cur_finished_at = t.get("finished_at")
    obj["dependents_count"] = t.get("dependents_count", '-1')
    obj["package_info"] = t.get("package_info", {})
    obj["version"] = t.get("version")
    obj["latest_version"] = t.get("latest_version", '-1')
    obj["ecosystem"] = t.get("ecosystem")
    obj["package"] = t.get("package")
    condition = [obj['package'] != None, obj['version'] != None, obj['ecosystem'] != None]
    if not all(condition):
        return None
    return obj, cur_finished_at


def _other_key_info(data_source, other_keys, bucket_name=None):
    obj = {"analyses": {}}
    for this_key in other_keys:
        value = data_source.read_json_file(this_key, bucket_name)
        this_key = this_key.split("/")[-1]
        obj["analyses"][this_key[:-len('.json')]] = value
    return obj
    

def _set_max_finished_at(max_finished_at, cur_finished_at, max_datetime, date_time_format):
    if max_finished_at is None:
        max_finished_at = cur_finished_at
    else:
        cur_datetime = datetime.strptime(cur_finished_at, date_time_format)
        if cur_datetime > max_datetime:
            max_finished_at = cur_finished_at
    return max_finished_at        


def _get_exception_msg(prefix, e):
    msg = prefix + ": " + str(e)
    logger.error(msg)
    tb = traceback.format_exc()
    logger.error("Traceback for latest failure in import call: %s" % tb)
    return msg
    

def _import_grouped_keys(data_source, dict_grouped_keys):
    logger.debug("Begin import...")
    date_time_format = "%Y-%m-%dT%H:%M:%S.%f"

    report = {'status': 'Success', 'message': 'The import finished successfully!'}
    count_imported_EPVs = 0
    max_finished_at = None
    max_datetime = None
    last_imported_EPV = None
    if len(dict_grouped_keys.items()) == 0:
        report['message'] = 'Nothing to be imported! No data found on S3 to be imported!'
    try:
        for counter, v in dict_grouped_keys.items():
            first_key = v[0]
            logger.debug("Importing " + first_key)
            logger.debug("File---- %s  numbered---- %d  added:" % (first_key, counter))
            obj, cur_finished_at = _first_key_info(data_source, first_key)
            if obj is None:
                continue
            obj_returned = _other_key_info(data_source, other_keys=v[1:])
            obj.update(obj_returned)

            GraphPopulator.populate_from_json(obj)
            count_imported_EPVs += 1
            last_imported_EPV = first_key
            
            max_finished_at = _set_max_finished_at(max_finished_at, cur_finished_at, max_datetime, date_time_format)
            max_datetime = datetime.strptime(max_finished_at, date_time_format)

    except Exception as e:
        msg = _get_exception_msg("The import failed", e)
        report['status'] = 'Failure'
        report['message'] = msg    

    report['count_imported_EPVs'] = count_imported_EPVs
    report['last_imported_EPV'] = last_imported_EPV
    report['max_finished_at'] = max_finished_at
    return report


def _import_keys_from_s3_http(data_source, epv_list):
    logger.debug("Begin import...")
    date_time_format = "%Y-%m-%dT%H:%M:%S.%f"

    report = {'status': 'Success', 'message': 'The import finished successfully!'}
    count_imported_EPVs = 0
    max_finished_at = None
    max_datetime = None
    last_imported_EPV = None
    epv = []
    for epv_key in epv_list:
        for key, contents in epv_key.items():
            if len(contents.get('package')) == 0 and len(contents.get('version')) == 0:
                report['message'] = 'Nothing to be imported! No data found on S3 to be imported!'
                continue
            try:
                # Check whether EPV meta is present and not error out
                first_key = contents['ver_key_prefix'] + '.json'
                obj, cur_finished_at = _first_key_info(data_source, first_key, config.AWS_EPV_BUCKET)
                if obj is None:
                    continue
                # Check other Version level information and add it to common object
                if len(contents.get('version')) > 0:
                    ver_obj = _other_key_info(data_source, contents.get('version'), config.AWS_EPV_BUCKET)
                    obj.update(ver_obj)

                # Check Package related information and add it to package object
                if len(contents.get('package')) > 0:
                    pkg_obj = _other_key_info(data_source, contents.get('package'), config.AWS_PKG_BUCKET)
                    obj.update(pkg_obj)

                # Create Gremlin Query
                str_gremlin = GraphPopulator.create_query_string(obj)

                # Fire Gremlin HTTP query now
                logger.info("Ingestion initialized for EPV - " +
                            obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version'))
                epv.append(obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version'))
                payload = {'gremlin': str_gremlin}
                response = requests.post(config.GREMLIN_SERVER_URL_REST, data=json.dumps(payload))
                resp = response.json()

                if resp['status']['code'] == 200:
                    count_imported_EPVs += 1
                    last_imported_EPV = first_key
                    max_finished_at = _set_max_finished_at(max_finished_at, cur_finished_at, max_datetime, date_time_format)
                    max_datetime = datetime.strptime(max_finished_at, date_time_format)

            except Exception as e:
                msg = _get_exception_msg("The import failed", e)
                report['status'] = 'Failure'
                report['message'] = msg

    report['epv'] = epv
    report['count_imported_EPVs'] = count_imported_EPVs
    report['last_imported_EPV'] = last_imported_EPV
    report['max_finished_at'] = max_finished_at

    return report


def _import_grouped_keys_http(data_source, dict_grouped_keys):
    logger.debug("Begin import...")
    date_time_format = "%Y-%m-%dT%H:%M:%S.%f"

    report = {'status': 'Success', 'message': 'The import finished successfully!'}
    count_imported_EPVs = 0
    max_finished_at = None
    max_datetime = None
    last_imported_EPV = None
    epv = []
    if len(dict_grouped_keys.items()) == 0:
        report['message'] = 'Nothing to be imported! No data found on S3 to be imported!'
    try:
        for counter, v in dict_grouped_keys.items():
            first_key = v[0]
            obj, cur_finished_at = _first_key_info(data_source, first_key)
            if obj is None:
                continue
            obj_returned = _other_key_info(data_source, other_keys=v[1:])
            obj.update(obj_returned)

            str_gremlin = GraphPopulator.create_query_string(obj)
            logger.debug("Importing " + first_key)
            logger.debug("File---- %s  numbered---- %d  added:" % (first_key, counter))

            # Fire Gremlin HTTP query now
            logger.info("Ingestion initialized for EPV - " +
                        obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version'))
            epv.append(obj.get('ecosystem') + ":" + obj.get('package') + ":" + obj.get('version'))
            payload = {'gremlin': str_gremlin}
            response = requests.post(config.GREMLIN_SERVER_URL_REST, data=json.dumps(payload))
            resp = response.json()

            if resp['status']['code'] == 200:
                count_imported_EPVs += 1
                last_imported_EPV = first_key
                max_finished_at = _set_max_finished_at(max_finished_at, cur_finished_at, max_datetime, date_time_format)
                max_datetime = datetime.strptime(max_finished_at, date_time_format)

        report['epv'] = epv

    except Exception as e:
        msg = _get_exception_msg("The import failed", e)
        report['status'] = 'Failure'
        report['message'] = msg

    report['count_imported_EPVs'] = count_imported_EPVs
    report['last_imported_EPV'] = last_imported_EPV
    report['max_finished_at'] = max_finished_at
    return report


def _log_report_msg(import_type, report):
    # Log the report
    msg = """
        Report from {}:
        {}
        Total number of EPVs imported: {}
        The last successfully imported EPV: {}
        Max value of 'finished_at' among all imported EPVs: {}
    """
    msg = msg.format(import_type, report.get('message'),
                     report.get('count_imported_EPVs'),
                     report.get('last_imported_EPV'),
                     report.get('max_finished_at'))

    if report.get('status') is 'Success':
        logger.debug(msg)
    else:
        # TODO: retry??
        logger.error(msg)  


def import_bulk(data_source, book_keeper):
    """
    Imports bulk data from the given data source.
    It can perform both 'full import' as well as 'incremental update'.

    :param data_source: Data source to read input from
    :param book_keeper: Book keeper to get info about recently ingested data
    :return: None
    """
    try:
        # Now, get the last incremental update timestamp from the graph.
        graph_meta = GraphPopulator.get_metadata()

        # If the timestamp is unknown then it means graph is not populated yet and we need to do full import.
        list_keys = []
        if graph_meta is None:
            # Collect all the files from data-source and group them by package-version.
            logger.debug("Performing full import. Fetching all objects from : " + data_source.get_source_name())
            list_keys = data_source.list_files()

        # else if the timestamp is available then we need to perform incremental update.
        else:
            if book_keeper is None:
                raise RuntimeError("Cannot perform incremental update without book keeper!")

            # Collect all the package-version from RDS table that were updated recently.
            # Note: If RDS table is unreachable then we should still live with S3 data.
            min_finished_at = graph_meta.last_incr_update_ts
            list_epv = book_keeper.get_recent_epv(min_finished_at)

            # Collect relevant files from data-source and group them by package-version.
            logger.debug("Performing incremental update. Fetching some objects from : " + data_source.get_source_name())
            for epv in list_epv:
                key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/" + epv.get('version')
                list_keys.extend(data_source.list_files(prefix=key_prefix))
        # end of if graph_meta is None:

        # Import the S3 data
        dict_grouped_keys = _group_keys_by_epv(list_keys, data_source)
        report = _import_grouped_keys(data_source, dict_grouped_keys)

        # In the end, update the meta-data in the graph.
        if report.get('max_finished_at') is not None:
            dict_graph_meta = {
                'last_incremental_update_timestamp': report.get('max_finished_at'),
                'last_imported_epv': report.get('last_imported_EPV')
            }
            GraphPopulator.update_metadata(dict_graph_meta)
        _log_report_msg("import_bulk()", report)

    except Exception as e:
        msg = _get_exception_msg("import_bulk() failed with error", e)
        raise RuntimeError(msg)

    return report


# Note: we don't update graph meta-data for this on-line 'unknown-path' scenario.
def import_epv(data_source, list_epv):
    try:
        # Collect relevant files from data-source and group them by package-version.
        list_keys = []
        for epv in list_epv:
            key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/" + epv.get('version')
            list_keys.extend(data_source.list_files(prefix=key_prefix))
        # end of if graph_meta is None:

        # Import the S3 data
        dict_grouped_keys = _group_keys_by_epv(list_keys, data_source)
        report = _import_grouped_keys(data_source, dict_grouped_keys)

        _log_report_msg("import epv()", report)

    except Exception as e:
        msg = _get_exception_msg("import_epv() failed with error", e)
        raise RuntimeError(msg)

    return report


def import_epv_http(data_source, list_epv):
    try:
        # Collect relevant files from data-source and group them by package-version.

        list_keys = []
        for epv in list_epv:
            dict_keys = {}
            ver_list_keys = []
            pkg_list_keys = []
            # Get EPV level keys
            ver_key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/" + epv.get('version')
            ver_list_keys.extend(data_source.list_files(bucket_name=config.AWS_EPV_BUCKET, prefix=ver_key_prefix))
            # Get Package level keys
            pkg_key_prefix = epv.get('ecosystem') + "/" + epv.get('name') + "/"
            pkg_list_keys.extend(data_source.list_files(bucket_name=config.AWS_PKG_BUCKET, prefix=pkg_key_prefix))

            dict_keys[ver_key_prefix] = {
                'version': ver_list_keys,
                'ver_key_prefix': ver_key_prefix,
                'package': pkg_list_keys,
                'pkg_key_prefix': pkg_key_prefix
            }
            list_keys.append(dict_keys)

        # end of if graph_meta is None:

        # Import the S3 data
        report = _import_keys_from_s3_http(data_source, list_keys)

        # Log the report
        _log_report_msg("import_epv()", report)

    except Exception as e:
        msg = _get_exception_msg("import_epv() failed with error", e)
        raise RuntimeError(msg)
    return report


def update_graph_metadata(input_json):
    GraphPopulator.update_metadata(input_json)


def import_from_s3():
    return import_bulk(S3DataSource(src_bucket_name=config.AWS_BUCKET,
                                    access_key=config.AWS_S3_ACCESS_KEY_ID,
                                    secret_key=config.AWS_S3_SECRET_ACCESS_KEY),
                       RDSBookKeeper(postgres_host=config.POSTGRESQL_HOST,
                                     postgres_port=config.POSTGRESQL_PORT,
                                     postgres_user=config.POSTGRESQL_USER,
                                     postgres_pass=config.POSTGRESQL_PASSWORD,
                                     postgres_db=config.POSTGRESQL_DATABASE))


# Note: Incremental update will not happen as we are passing book_keeper=None
def import_from_folder(src_dir):
    return import_bulk(data_source=LocalFileSystem(src_dir), book_keeper=None)


def import_epv_from_s3(list_epv):
    return import_epv(S3DataSource(src_bucket_name=config.AWS_BUCKET,
                                   access_key=config.AWS_S3_ACCESS_KEY_ID,
                                   secret_key=config.AWS_S3_SECRET_ACCESS_KEY),
                      list_epv)


def import_epv_from_s3_http(list_epv):
    return import_epv_http(S3DataSource(src_bucket_name=config.AWS_BUCKET,
                                        access_key=config.AWS_S3_ACCESS_KEY_ID,
                                        secret_key=config.AWS_S3_SECRET_ACCESS_KEY),
                           list_epv)


def import_epv_from_folder(src_dir, list_epv):
    return import_epv(LocalFileSystem(src_dir), list_epv)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-s", "--source", dest="source",
                      help="Source can be S3 or DIR", metavar="SOURCE")
    parser.add_option("-d", "--directory", dest="directory",
                      help="Read from DIRECTORY", metavar="DIRECTORY")

    (options, args) = parser.parse_args()

    source = "S3"
    if options.source is None:
        logger.info ("No source provided")
    else:
        if options.source.upper() == "DIR":
            source = "DIR"
            if options.directory is None:
                logger.info ("Directory path not provided")
                sys.exit(-1)

    if source == "S3":
        import_from_s3()
    elif source == "DIR":
        import_from_folder(options.directory)
    else:
        logger.info ("Invalid CLI arguments")
        sys.exit(-1)
