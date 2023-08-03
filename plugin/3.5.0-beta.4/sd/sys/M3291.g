; A message passing queue for use by DuetLapse3
; This is not used as a FIFO queue but more a message buffer.

; The macro should be placed in /sys folder and given a name like
; M3921 (the default)
;
; If the name is changed e.g. to avaid a custom M code conflict (should always be M<something>)
; the -M3291 option of DuetLapse3 needs to be set to the new name
;
; Useage:
; M3921 B"<DuetLapse3 command message>"
; e.g. M3921 B"Duetlapse3.start"
; There can only be one message per call
;
; Special Useage:
; M3921 B"Init"    (Case Sensitive)
; Does nothing - make sure the globals are initialized
;
; M3921 B"Clear"    (Case Sensitive)
; Clears the queue and leaves the sequence number at last value.  May be useful between print jobs
;
; M3921 B"Del"    (Case Sensitive)
; Deletes items from the queue based on indexes held in global.DL3del
;
;DL3msg queue uses the following structures
;DL3msg[0]  int - sequence number of last message added.
;DL3msg(x}  string -  the message to be processed
;
;DL3del[0]  array of indexes in DL3msg to be deleted
; e.g.  set DL3del[0] = {1,3,7,}
;
; At the processing end, if DL3msg[0] is > last time checked: all messages are extracted in one go, DL3del is set and then M321 P"Del" called.
; i.e. the recently read entries are cleared
;
; #################  MACRO STARTS HERE #################################
; make sure queue is initialized.  Calling without B parameter will achieve
var len_DL3msg = 15								; number of messages that can be held 15 should be good for most cases
if !exists(global.DL3msg) || global.DL3msg=null
	global DL3msg = vector(var.len_DL3msg,null)
	set global.DL3msg[0] = 0					;beginning sequence number
if !exists(global.DL3del) || global.DL3del=null
	global DL3del = vector(1,null)						; Items, by index to delete

var Bparam = null 

; check if B parameter sent
if !exists(param.B)
  abort "M3291  -- No message was passed."
  
set var.Bparam = param.B


if var.Bparam = "Init"
	; Do nothing
	; Can be used to initialize the globals
	echo "DL3msg queue initialized"

elif var.Bparam = "Clear"
	; Clear the queue
	; sets all message slots to null but leaves the sequence number as-is
	while true
		if iterations >= var.len_DL3msg
			break
		var sequence = global.DL3msg[0]
		set global.DL3msg = vector(var.len_DL3msg,null)
		set global.DL3msg[0] = var.sequence  
	echo "DL3msg queue cleared"

elif var.Bparam = "Del"
	; Delete (make null) selected messages from the queue
	; This allows bulk deletes
	; Items to be deleted are held in an array in global.DL3del
	if global.DL3del[0] != null            ; there are items to delete
		var deletelist = global.DL3del[0]
		while true
			if iterations >= #var.deletelist
				break
			set global.DL3msg[var.deletelist[iterations]] = null
		set global.DL3del[0] = null
		echo "DL3msg queue items deleted"
	else
		echo "Nothing to delete"
else
	; Add new message to the queue
	; Iterate through and place message in any emply (null) slot
	; If all the slots are full -- stop adding messages				
	var success = false
	while true
		if iterations >= var.len_DL3msg
			break
		if global.DL3msg[iterations] == null
			set global.DL3msg[0] = global.DL3msg[0] + 1 ; increment message count
			set global.DL3msg[iterations] = var.Bparam
			set var.success = true
			echo var.Bparam^" added to DL3msg queue" 
			break
	; Check if message added OK		
	if !var.success
		var errormsg = "Error! - DL3msg queue was full"
		M291 P{var.errormsg} S2
		echo var.errormsg
