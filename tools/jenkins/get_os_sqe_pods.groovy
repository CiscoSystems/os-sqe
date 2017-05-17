def shell(String command)
{
	def sout = new StringBuilder(), serr = new StringBuilder()
	def proc = command.execute()
	proc.consumeProcessOutput(sout, serr)
	proc.waitForOrKill(1000)
	return "$sout $serr"
}

def pods = ['-----']

def url = 'http://gitlab.cisco.com/openstack-cisco-dev/osqe-configs/tree/master/lab_configs'
ans = shell('curl ' + url)

def regex = /title="[\w-]+\.yaml"/  // match things like title="marahaika-vts.yaml"
def find_names = (ans =~ /$regex/)
find_names.each{ s ->
  pods.push(s.stripIndent(6))
}
return pods.toSet().sort()