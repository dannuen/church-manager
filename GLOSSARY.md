# Church Manager

An offline database that helps one senior pastor run one church: its people, calendar, money, documents and pastoral care. Each church has its own copy.

## People

**Person**:
Anyone the church knows about, whether member, visitor, child, someone who left or someone who passed away.
_Avoid_: Member (that is a status), contact, user

**Status**:
Where a person stands with the church right now, such as Member, Attender, Visitor, Left or Passed away. Each change is kept with its date.
_Avoid_: Type, category

**Family**:
A group of people who share one address. A person is in at most one family at a time; past family links are kept with dates. A person with no family keeps their own address.
_Avoid_: Household

**Chi phái**:
A group of families in one area. A family is in at most one chi phái at a time; past links are kept with dates.
_Avoid_: Area, zone, cell group

**Trưởng Chi phái**:
The one person who leads a chi phái. Past leaders are kept with dates.
_Avoid_: Area leader

**Family role**:
A person's place in their family: Head, Spouse, Child or Other.

**Ministry**:
A serving team in the church, such as Worship, Youth or Children.
_Avoid_: Department, group, team

**Ministry role**:
How a person is part of a ministry: Leader or Member.

**Private note**:
A note only the pastor sees, such as counseling or prayer. Never part of a handover.
_Avoid_: Secret note

## Calendar

**Calendar item**:
Anything with a date and time: a service, meeting, visit or event. It can list people who join or serve, and can repeat.
_Avoid_: Schedule, appointment, activity

**Service**:
A worship gathering, such as Sunday service.
_Avoid_: Mass, meeting

**Head count**:
The number of people at one service, with a note about who was absent.
_Avoid_: Attendance record

## Money

**Offering**:
Money given to the church, with an amount, a fund and an optional giver.

**Giver**:
The person or family an offering is from. An offering with no giver is a no-name offering.
_Avoid_: Donation, tithe, income

**Fund**:
Where an offering goes, such as General, Building or Missions.

**Expense**:
Money the church spends, with an amount and a spending category.
_Avoid_: Cost, spending, payment

**Spending category**:
What an expense is for, such as Rent, Utilities or Events.

**Giving statement**:
A yearly list of one giver's offerings, for a person or a family.
_Avoid_: Receipt, tax letter

## Care

**Visit**:
A calendar item where the pastor visits a person or family. Done visits make up the care log.
_Avoid_: Pastoral call, home visit

**Care log**:
All done visits: who, when and a short note.

**Needs a visit**:
A person whose last pastoral visit is older than the care reminder time (3 months by default).

## Documents

**Document**:
A file kept inside the church copy, linked to a person, family or calendar item.
_Avoid_: Attachment, upload

**Sent document**:
A document the church sends out, with a date, a recipient, a purpose and a number per year (such as 05/2026).
_Avoid_: Letter, outgoing mail

**Recipient**:
The outside body a sent document goes to: Chính quyền (government), Giáo hội (denomination) or Hội Thánh (another church). The list is editable.

**Purpose**:
Why a sent document is sent, such as Invitation, Notice, Certificate or Report. The list is editable.

## Copies

**Church copy**:
One church's whole database in one file plus its documents folder.
_Avoid_: Instance, install, tenant

**Handover**:
Giving the church copy to the next pastor of the same church, with private notes removed.

**New church setup**:
Starting a blank church copy that keeps only the default lists.
