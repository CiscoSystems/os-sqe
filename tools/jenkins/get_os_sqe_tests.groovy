def shell(String command)
{
	def sout = new StringBuilder(), serr = new StringBuilder()
	def proc = command.execute()
	proc.consumeProcessOutput(sout, serr)
	proc.waitForOrKill(1000)
	return "$sout $serr"
}

def tests = []
if (starts_with.startsWith('perf'))
	tests = ['perf-csr-0', 'perf-csr']
else if (starts_with.startsWith('vts'))
    tests = ['vts']


def url = 'https://wwwin-gitlab-sjc.cisco.com/mercury/os-sqe/tree/master/configs/ha'
ans = shell('curl ' + url)

def regex = /title="[\w-]+\.yaml"/  // match things like title="xxx-vts.yaml"
def find_names = (ans =~ /$regex/)
find_names.each{ s ->
  a = s.stripIndent(6).replace('"', '')
  if (a.startsWith(starts_with))
  	tests.push(a)
}
return tests.toSet().sort()