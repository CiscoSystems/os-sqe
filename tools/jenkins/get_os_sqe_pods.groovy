def shell(String command)
{
	def sout = new StringBuilder(), serr = new StringBuilder()
	def proc = command.execute()
	proc.consumeProcessOutput(sout, serr)
	proc.waitForOrKill(1000)
	return "$sout $serr"
}

def pods = []

ans = shell('curl https://wwwin-gitlab-sjc.cisco.com/mercury/configs/tree/master')

def regex = /title="[\w-]+\.yaml"/  // match things like title="marahaika-vts.yaml"
def find_names = (ans =~ /$regex/)
find_names.each{ s ->
  pods.push(s.stripIndent(6).replace('"', ''))
}
return pods.toSet().sort()