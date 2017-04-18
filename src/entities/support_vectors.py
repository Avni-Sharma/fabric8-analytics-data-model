from entities.entity_base import EntityBase
import time
import logging

logger = logging.getLogger(__name__)


class LicenseDetails(EntityBase):
    label = "License"

    def __init__(self, name=''):
        super(LicenseDetails, self).__init__()
        self.name = name
        self.label = LicenseDetails.label
        self.last_updated = None
    # TODO: Add Edge org->approved->license

    @classmethod
    def load_from_json(cls, license_data):
        license_details_list = []
        license_names = set()
        counts_list = []

        if (license_data is not None and
                "summary" in license_data and
                "distinct_licenses" in license_data["summary"]):
            distinct_licenses = license_data["summary"]["distinct_licenses"]

            for dl in distinct_licenses:
                license_names.add(dl.get("license_name", '-1'))
                license_details_list.append(
                    LicenseDetails(dl.get("license_name", '-1')))
                counts_list.append(dl.get("count", -1))

        return license_details_list, counts_list, license_names

    def save(self):
        license_criteria = {'lname': self.name}
        present_license = LicenseDetails.find_by_criteria(
            self.label, license_criteria)
        if present_license is None:
            return self.create()
        else:
            self.id = present_license.id
            return self.update()

    @classmethod
    def return_entity_obj(cls, name, id, last_updated):
        objlicense = LicenseDetails(name)
        objlicense.last_updated = last_updated
        objlicense.id = id
        return objlicense

    @classmethod
    def find_by_criteria(cls, label, criteria_dict):
        try:
            query = cls.g().V().has('vertex_label', label)
            for k, v in criteria_dict.items():
                query = query.has(k, v)
            check_license = query.toList()
            logger.debug("query sent:------ %s" % query)
            logger.debug("query_result:----- %s" % check_license)
            if len(check_license) == 0:
                return None
            else:
                values = cls.g().V(check_license[0].id).valueMap().toList()[0]
                return cls.return_entity_obj(values.get('lname')[0], check_license[0].id, values.get('last_updated')[0])

        except Exception as e:
            logger.error("find_by_criteria() failed: %s" % e)
            return None

    def create(self):
        try:
            license_criteria = {'lname': self.name}
            present_license = LicenseDetails.find_by_criteria(
                self.label, license_criteria)
            if present_license is None:
                ts = time.time()
                results = self.g().addV(self.label). \
                    property('vertex_label', self.label). \
                    property('lname', self.name).\
                    property('last_updated', ts).\
                    toList()
                logger.debug("create() %s - results: %s" %
                             (self.label, results))

                self.last_updated = ts
                self.id = results[0].id
                logger.debug("Vertex ID : %s, %s: %s" %
                            (self.id, self.label, self))
                
                logger.info("---Create--- %s ---NEW = %d"%(self.label, self.id))

                return self.id
            else:
                logger.debug("License exists: %s " %
                             present_license.id)
                self.last_updated = present_license.last_updated
                self.id = present_license.id
                
                logger.info("---Create--- %s ---EXISTS = %d"%(self.label, self.id))

                return self.id

        except Exception as e:
            logger.error("create() failed: %s" % e)
            return None

    def update(self):
        try:
            ts = time.time()
            results = self.g().V(self.id). \
                property('vertex_label', self.label). \
                property('lname', self.name).\
                property('last_updated', ts).\
                toList()

            self.last_updated = ts
            logger.debug("update() %s - results: %s" % (self.label, results))
            logger.debug("Vertex ID : %s, %s: %s" % (self.id, self.label, self))
            
            logger.info("---Update--- %s = %d"%(self.label, self.id))

            return self.id

        except Exception as e:
            logger.error("update() failed: %s" % e)
            return None


class SecurityDetails(EntityBase):
    label = 'CVE'

    def __init__(self, cve_id='-1', cvss='-1', summary='-1', **issue):
        super(SecurityDetails, self).__init__()
        self.cve_id = cve_id
        self.cvss = float(cvss)
        self.summary = str(summary)
        self.references = []
        self.access = {}
        self.impact = {}
        self.label = SecurityDetails.label
        if len(issue) is not 0:
            self.bl_base_score = issue.get('baseScore', -1)
            self.bl_description = issue.get('description', '-1')
            self.bl_exploitability_subscore = issue.get('exploitabilitySubscore', -1)
            self.bl_impact_subscore = issue.get('impactSubscore', -1)
            self.bl_remediation_status = issue.get('remediationStatus', '-1')
            self.bl_remediation_updated_at = issue.get('remediationUpdatedAt', '-1')
            self.bl_remediation_created_at = issue.get('remediationCreatedAt', '-1')
            self.bl_severity = issue.get('severity', '-1')
            self.bl_source = issue.get('source', '-1')
            self.bl_vulnerability_name = issue.get('vulnerabilityName', '-1')
            self.bl_vulnerability_published_date = issue.get('vulnerabilityPublishedDate', '-1')
            self.bl_vulnerability_updated_date = issue.get('vulnerabilityUpdatedDate', '-1')
        self.last_updated = None

    def issue_has_references(self, link):
        self.references.append(str(link))

    def issue_has_access(self, access_type, access_value):
        self.access[access_type] = str(access_value)

    def issue_has_impact(self, impact_type, impact_value):
        self.impact[impact_type] = str(impact_value)

    @classmethod
    def load_from_json(cls, security_data):
        security_obj_list = []
        cvss_list = []
        cve_id_list = []
        if(len(security_data.get("summary", [])) != 0):
            security_list = []
            for security_value in security_data["details"]:
                cvss = security_value.get('cvss', {}).get('score', 0)

                security_list.append((security_value.get('id'), cvss, security_value.get('summary'), security_value.get('references'),
                                      security_value.get('access'), security_value.get('impact')))
            for s in security_list:
                objsecurity = SecurityDetails(s[0], s[1], s[2])
                if s[3] is not None:
                    for link in s[3]:
                        objsecurity.issue_has_references(link)
                if s[4] is not None:
                    for t, v in s[4].items():
                        objsecurity.issue_has_access(t, v)
                if s[5] is not None:
                    for t, v in s[5].items():
                        objsecurity.issue_has_impact(t, v)
                security_obj_list.append(objsecurity)
                cvss_list.append(objsecurity.cvss)
                cve_id_list.append(objsecurity.cve_id)

        return security_obj_list, cvss_list, cve_id_list

    def save(self):
        security_criteria = {'cve_id': self.cve_id}
        present_security = SecurityDetails.find_by_criteria(
            self.label, security_criteria)
        if present_security is None:
            return self.create()
        else:
            self.id = present_security.id
            return self.update()

    @classmethod
    def return_entity_obj(cls, cve_id, cvss, summary, references, id, last_updated):
        objsecurity = SecurityDetails(cve_id, cvss, summary)
        objsecurity.references = references
        objsecurity.last_updated = last_updated
        objsecurity.id = id
        return objsecurity

    @classmethod
    def find_by_criteria(cls, label, criteria_dict):
        try:
            query = cls.g().V().has('vertex_label', label)
            for k, v in criteria_dict.items():
                query = query.has(k, v)
            check_security = query.toList()
            logger.debug("query sent:------ %s" % query)
            logger.debug("query_result:----- %s" % check_security)
            if len(check_security) == 0:
                return None
            else:
                values = cls.g().V(check_security[0].id).valueMap().toList()[0]
                return cls.return_entity_obj(values.get('cve_id')[0], values.get('cvss')[0], 
                                            values.get('summary')[0], 
                                            values.get('references'),
                                            check_security[0].id, values.get('last_updated')[0])

        except Exception as e:
            logger.error("find_by_criteria() failed: %s" % e)
            return None

    def create(self):
        try:
            security_criteria = {'cve_id': self.cve_id}
            present_security = SecurityDetails.find_by_criteria(
                self.label, security_criteria)
            if present_security is None:
                ts = time.time()
                query = self.g().addV(self.label).\
                    property('vertex_label', self.label). \
                    property('cve_id', self.cve_id).\
                    property('cvss', self.cvss).\
                    property('summary', self.summary or '-1').\
                    property('access_authentication', self.access.get('authentication') or '-1').\
                    property('access_complexity', self.access.get('complexity') or '-1').\
                    property('access_vector', self.access.get('vector') or '-1').\
                    property('impact_availability', self.impact.get('availability') or '-1').\
                    property('impact_confidentiality', self.impact.get('confidentiality') or '-1').\
                    property('impact_integrity', self.impact.get('integrity') or '-1').\
                    property('last_updated', ts)

                for r in self.references:
                    query.property('references', r)
                
                results = query.toList()    

                logger.debug("create() %s - results: %s" %
                             (self.label, results))

                self.last_updated = ts
                self.id = results[0].id
                logger.debug("Vertex ID : %s, %s: %s" %
                            (self.id, self.label, self))
                
                logger.info("---Create--- %s ---NEW = %d"%(self.label, self.id))

                return self.id
            else:
                logger.debug("CVE exists: %s " %
                             present_security.id)
                self.last_updated = present_security.last_updated
                self.id = present_security.id
                
                logger.info("---Create--- %s ---EXISTS = %d"%(self.label, self.id))

                return self.id

        except Exception as e:
            logger.error("create() failed: %s" % e)
            return None

    def update(self):
        try:
            ts = time.time()
            query = self.g().V(self.id).\
                property('vertex_label', self.label). \
                property('cvss', self.cvss).\
                property('summary', self.summary or '-1').\
                property('access_authentication', self.access.get('authentication') or '-1').\
                property('access_complexity', self.access.get('complexity') or '-1').\
                property('access_vector', self.access.get('vector') or '-1').\
                property('impact_availability', self.impact.get('availability') or '-1').\
                property('impact_confidentiality', self.impact.get('confidentiality') or '-1').\
                property('impact_integrity', self.impact.get('integrity') or '-1').\
                property('last_updated', ts)
                
            for r in self.references:
                query.property('references', r)

            results = query.toList()    

            self.last_updated = ts
            logger.debug("update() %s - results: %s" % (self.label, results))
            logger.debug("Vertex ID : %s, %s: %s" % (self.id, self.label, self))
            
            logger.info("---Update--- %s = %d"%(self.label, self.id))

            return self.id

        except Exception as e:
            logger.error("update() failed: %s" % e)
            return None

    def add_blackduck_data(self, issue):
        if len(issue) is not 0:
            self.bl_base_score = issue.get('baseScore', -1)
            self.bl_description = issue.get('description', '-1')
            self.bl_exploitability_subscore = issue.get('exploitabilitySubscore', -1)
            self.bl_impact_subscore = issue.get('impactSubscore', -1)
            self.bl_remediation_status = issue.get('remediationStatus', '-1')
            self.bl_remediation_updated_at = issue.get('remediationCreatedAt', '-1')
            self.bl_remediation_created_at = issue.get('remediationUpdatedAt', '-1')
            self.bl_severity = issue.get('severity', '-1')
            self.bl_source = issue.get('source', '-1')
            self.bl_vulnerability_name = issue.get('vulnerabilityName', '-1')
            self.bl_vulnerability_published_date = issue.get('vulnerabilityPublishedDate', '-1')
            self.bl_vulnerability_updated_date = issue.get('vulnerabilityUpdatedDate', '-1')

            try:
                ts = time.time()
                results = self.g().V(self.id). \
                    property('base_score', self.bl_base_score).\
                    property('description', self.bl_description).\
                    property('exploitability_subscore', self.bl_exploitability_subscore).\
                    property('impact_subscore', self.bl_impact_subscore).\
                    property('remediation_status', self.bl_remediation_status).\
                    property('remediation_updated_at', self.bl_remediation_updated_at).\
                    property('remediation_created_at', self.bl_remediation_created_at).\
                    property('severity', self.bl_severity).\
                    property('source', self.bl_source).\
                    property('vulnerability_name', self.bl_vulnerability_name).\
                    property('vulnerability_published_date', self.bl_vulnerability_published_date).\
                    property('vulnerability_updated_date', self.bl_vulnerability_updated_date).\
                    property('last_updated', ts).\
                    toList()

                self.last_updated = ts

                logger.debug("add_blackduck_cve() %s - results: %s" % (self.label, results))
                logger.debug("Vertex ID : %s, %s: %s" % (self.id, self.label, self))

            except Exception as e:
                logger.error("add_blackduck_cve() failed: %s" % e)
