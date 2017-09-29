def shell(String command)
{
	def sout = new StringBuilder(), serr = new StringBuilder()
	def proc = command.execute()
	proc.consumeProcessOutput(sout, serr)
	proc.waitForOrKill(1000)
	return "$sout $serr"
}

def tests = [starts_with]

def url = 'https://wwwin-gitlab-sjc.cisco.com/mercury/os-sqe/tree/master/configs/ha'
ans = shell('curl ' + url)


def regex = /title="${starts_with}.*\.yaml"/  // match things like title="xxx01-vts.yaml"
def find_names = (ans =~ /$regex/)
find_names.each{ s ->
  a = s.split(' ')[0]
  b = a.stripIndent(6).replace('"', '')
  tests.push(b)
}
return tests.toSet().sort()