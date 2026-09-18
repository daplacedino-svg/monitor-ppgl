# Cria (ou recria) a tarefa "Monitor PPGL" no Agendador de Tarefas do Windows.
# Executa coletar.py a cada hora, sem abrir janela, enquanto voce estiver logado.
# Uso (PowerShell, na pasta do projeto):  .\agendar_tarefa.ps1
# Para remover:  Unregister-ScheduledTask -TaskName "Monitor PPGL" -Confirm:$false

param(
    [int]$IntervaloMinutos = 60,
    [string]$Python = "C:\Python313\pythonw.exe"
)

$pasta = $PSScriptRoot
if (-not (Test-Path $Python)) { throw "Python nao encontrado em $Python. Informe com -Python <caminho do pythonw.exe>" }

$acao = New-ScheduledTaskAction -Execute $Python -Argument "`"$pasta\coletar.py`"" -WorkingDirectory $pasta
$gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervaloMinutos)
$opcoes = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Monitor PPGL" -Action $acao -Trigger $gatilho -Settings $opcoes `
    -Description "Coleta o Line-Up da APPA (bercos 141/142) e publica o site" -Force | Out-Null

Write-Host "Tarefa 'Monitor PPGL' criada: a cada $IntervaloMinutos min. Log em $pasta\logs\coletor.log"
