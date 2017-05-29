def shell(String command)
{
	def sout = new StringBuilder(), serr = new StringBuilder()
	def proc = command.execute()
	proc.consumeProcessOutput(sout, serr)
	proc.waitForOrKill(1000)
	return "$sout $serr"
}

def tests = []

def url = 'https://github.com/CiscoSystems/os-sqe/tree/master/configs/ha'
ans = shell('curl ' + url)

def regex = /title="[\w-]+\.yaml"/  // match things like title="tc-xxx-vts.yaml"
def find_names = (ans =~ /$regex/)
find_names.each{ s ->
  a = s.stripIndent(6).replace('"', '')
  if (a.startsWith(starts_with))
  	tests.push(a)
}
return tests.toSet().sort()