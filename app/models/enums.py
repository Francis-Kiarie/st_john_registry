import enum

class DivisionType(str, enum.Enum):
    adult = "adult"
    cadet = "cadet"
    nursing = "nursing"
    dolphin_pod = "dolphin_pod"

class MemberRank(str, enum.Enum):
    member = "member"
    corporal = "corporal"
    sergeant = "sergeant"
    acting_div_officer = "acting_div_officer"
    div_officer = "div_officer"
    div_superintendent = "div_superintendent"

class SpecialistTrack(str, enum.Enum):
    none = "none"
    med_student = "med_student"
    registered_surgeon = "registered_surgeon"
    nursing_student = "nursing_student"
    registered_nursing_officer = "registered_nursing_officer"
    emt_student = "emt_student"
    registered_paramedic = "registered_paramedic"

class MemberStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    discharged = "discharged"
    transferred = "transferred"
    deceased = "deceased"

class DutyType(str, enum.Enum):
    public_duty = "public_duty"
    community_service = "community_service"
    divisional_meeting = "divisional_meeting"
    parade = "parade"
    training = "training"

class UnitStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"

class AwardCategory(str, enum.Enum):
    meritorious = "meritorious"
    bravery = "bravery"
    service = "service"
    donation = "donation"
    program = "program"
    state_honour = "state_honour"
    divisional = "divisional"