# ecoding: utf-8

try:
    import dns.resolver
    no_dnspython = False
except:
    no_dnspython = True
import subprocess


def _get_txt_dns_record_from_lib(domain):
    try:
        records = dns.resolver.resolve(domain, 'TXT')
    except AttributeError:
        records = dns.resolver.query(domain, 'TXT')
    if len(records):
        return str(records[0]).replace('"', "").split(' ')


def _get_txt_dns_record_from_cmd(domain):
    cmd = ["host", "-t", "TXT", domain]
    out = subprocess.check_output(cmd)
    out = str(out.decode("UTF-8"))
    pre = "%s descriptive text " % domain
    if not out.startswith(pre):
        raise Exception("Cannot load text record from domain %s" % domain)
    return out.replace(pre, "").replace("\n", "").replace('"', "").split(' ')


def get_txt_dns_record(domain):
    if no_dnspython:
        return _get_txt_dns_record_from_cmd(domain)
    else:
        return _get_txt_dns_record_from_lib(domain)
